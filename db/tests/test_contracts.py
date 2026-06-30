"""Contract tests — keep the seams honest (fail if DDL/schema drifts from BACKEND.md).

* ClickHouse `events`/`alerts`/`dispositions` columns MUST match BACKEND.md §1/§2/§5.
* The audit Avro schema MUST cover every AuditAction.
* MinIO policies MUST be least-privilege (no principal gets `*` on everything).
* The registry metadata MUST carry the six required fields.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CH = REPO / "db" / "clickhouse" / "ddl"
BACKEND_MD = REPO / "BACKEND.md"


# ---------------------------------------------------------------------------
# helpers: pull the canonical JSON contracts out of BACKEND.md
# ---------------------------------------------------------------------------
def _json_blocks_by_section() -> dict:
    """Map '## N' section number -> list of parsed ```json blocks under it."""
    text = BACKEND_MD.read_text(encoding="utf-8")
    current = None
    blocks: dict = {}
    in_json = False
    buf: list = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(\d+)\.", line)
        if m:
            current = m.group(1)
            blocks.setdefault(current, [])
        if line.strip().startswith("```json"):
            in_json, buf = True, []
            continue
        if in_json and line.strip().startswith("```"):
            in_json = False
            try:
                blocks[current].append(json.loads("\n".join(buf)))
            except Exception:
                pass
            continue
        if in_json:
            buf.append(line)
    return blocks


def _flatten_l0(obj: dict) -> set:
    cols = set()
    for k, v in obj.items():
        if isinstance(v, dict):
            for sub in v:
                cols.add(f"{k}_{sub}")
        else:
            cols.add(k)
    return cols


def _ddl(name: str) -> str:
    return (CH / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# ClickHouse ↔ BACKEND.md parity
# ---------------------------------------------------------------------------
def test_events_table_mirrors_l0_event_field_for_field():
    blocks = _json_blocks_by_section()
    l0 = blocks["1"][0]
    expected = _flatten_l0(l0)
    ddl = _ddl("01_events.sql")
    missing = [c for c in expected if not re.search(rf"\b{re.escape(c)}\b", ddl)]
    assert not missing, f"events DDL missing L0 columns (BACKEND.md §1): {missing}"


def test_alerts_table_mirrors_l6_alert():
    blocks = _json_blocks_by_section()
    alert = blocks["2"][0]
    ddl = _ddl("03_alerts.sql")
    # top-level alert keys (reason_codes sub-fields checked separately)
    for key in alert:
        assert re.search(
            rf"\b{re.escape(key)}\b", ddl
        ), f"alerts DDL missing §2 field: {key}"
    # reason_codes nested sub-fields used across sources
    for sub in ("source", "code", "feature", "detail", "contribution"):
        assert re.search(
            rf"\b{sub}\b", ddl
        ), f"alerts.reason_codes missing sub-field: {sub}"


def test_dispositions_table_mirrors_edd_payload():
    blocks = _json_blocks_by_section()
    disp_blocks = blocks["5"]
    keys = set()
    for b in disp_blocks:
        keys |= set(b.keys())
    ddl = _ddl("04_dispositions.sql")
    # BACKEND.md §5 fields (request + response). feedback_queued_for_retraining is
    # stored as `feedback_queued`; status as `resulting_status` (documented).
    aliases = {
        "feedback_queued_for_retraining": "feedback_queued",
        "status": "resulting_status",
    }
    for key in keys:
        token = aliases.get(key, key)
        assert re.search(
            rf"\b{re.escape(token)}\b", ddl
        ), f"dispositions DDL missing §5 field: {key} ({token})"


def test_scores_records_model_version():
    ddl = _ddl("02_scores.sql")
    assert re.search(
        r"\bmodel_version\b", ddl
    ), "scores must record model_version on every row (Part 23.4)"


def test_tables_declare_hot_cold_tiering():
    for f in ("01_events.sql", "03_alerts.sql", "04_dispositions.sql"):
        ddl = _ddl(f)
        assert "storage_policy = 'tiered'" in ddl, f"{f} missing tiered storage policy"
        assert (
            "TO VOLUME 'cold'" in ddl and "TO VOLUME 'archive'" in ddl
        ), f"{f} missing TTL-MOVE"


# ---------------------------------------------------------------------------
# audit Avro ↔ AuditAction parity
# ---------------------------------------------------------------------------
def test_avsc_enum_matches_audit_action_enum():
    from services.audit.audit_schema import AuditAction

    avsc = json.loads(
        (REPO / "infra" / "audit" / "kafka" / "audit_event.avsc").read_text()
    )
    action_field = next(f for f in avsc["fields"] if f["name"] == "action")
    symbols = set(action_field["type"]["symbols"])
    assert symbols == {
        a.value for a in AuditAction
    }, "avsc action enum drifted from AuditAction"


def test_avsc_envelope_validates_a_built_record():
    import fastavro
    from services.audit.audit_schema import AuditAction, TargetType, build_envelope

    schema = fastavro.parse_schema(
        json.loads(
            (REPO / "infra" / "audit" / "kafka" / "audit_event.avsc").read_text()
        )
    )
    rec = build_envelope(
        audit_id="aud_abc123",
        ts="2026-06-30T00:00:00.000Z",
        actor_id="EMP-1",
        action=AuditAction.PII_UNMASK,
        target_type=TargetType.ENTITY,
        target_id="EMP-2",
        details={"justification": "case alr_1"},
    )
    assert fastavro.validation.validate(rec, schema, raise_errors=True)


# ---------------------------------------------------------------------------
# MinIO least-privilege policies
# ---------------------------------------------------------------------------
POLICY_DIR = REPO / "infra" / "storage" / "minio" / "policies"


def test_no_policy_grants_star_on_everything():
    for pf in POLICY_DIR.glob("*.json"):
        pol = json.loads(pf.read_text())
        for stmt in pol["Statement"]:
            if stmt["Effect"] != "Allow":
                continue
            actions = (
                stmt["Action"] if isinstance(stmt["Action"], list) else [stmt["Action"]]
            )
            resources = (
                stmt["Resource"]
                if isinstance(stmt["Resource"], list)
                else [stmt["Resource"]]
            )
            grants_all_actions = any(a == "s3:*" for a in actions)
            grants_all_resources = any(r in ("*", "arn:aws:s3:::*") for r in resources)
            assert not (
                grants_all_actions and grants_all_resources
            ), f"{pf.name} grants *:* (not least-privilege)"


def test_audit_writer_denies_delete():
    pol = json.loads((POLICY_DIR / "audit-writer.json").read_text())
    deny = [s for s in pol["Statement"] if s["Effect"] == "Deny"]
    denied = {
        a
        for s in deny
        for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
    }
    assert "s3:DeleteObject" in denied and "s3:DeleteObjectVersion" in denied


def test_models_reader_cannot_write():
    pol = json.loads((POLICY_DIR / "models-reader.json").read_text())
    deny = [s for s in pol["Statement"] if s["Effect"] == "Deny"]
    denied = {
        a
        for s in deny
        for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
    }
    assert "s3:PutObject" in denied


def test_datasets_rw_denied_models_and_audit():
    pol = json.loads((POLICY_DIR / "datasets-rw.json").read_text())
    deny = [s for s in pol["Statement"] if s["Effect"] == "Deny"]
    resources = {
        r
        for s in deny
        for r in (s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]])
    }
    assert any("models" in r for r in resources) and any(
        "audit-archive" in r for r in resources
    )


# ---------------------------------------------------------------------------
# registry layout six-field metadata
# ---------------------------------------------------------------------------
def test_registry_requires_six_metadata_fields():
    from registry.mlflow.config import REQUIRED_METADATA

    assert set(REQUIRED_METADATA) == {
        "dataset_hash",
        "params",
        "metrics",
        "training_code_commit",
        "approver",
        "signature",
    }
