"""Red-team: cross-workstream CONTRACT conformance (the seams).

Each workstream tests its OWN side; nothing tests that DATA's L0 event, ML's L6 Alert, the
BACKEND Alert schema, and the narrate() response all agree with the canonical BACKEND.md
contract. Drift here = silent integration breakage. Static (reads source), runs in any venv.
Blueprint: BACKEND.md §1/§2/§7, Part 5.1, Part 24.5, Part 25.6.
"""

from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(rel: str) -> str:
    p = os.path.join(REPO, rel)
    with open(p, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


# Canonical contracts (BACKEND.md is the source of truth).
L6_ALERT_KEYS = {
    "alert_id",
    "entity_id",
    "risk_score",
    "severity",
    "confidence",
    "status",
    "created_ts",
    "contributing_layers",
    "reason_codes",
    "exposure_inr",
    "sla_due_ts",
    "pii_tokenized",
}
NARRATE_KEYS = {"narrative", "provider", "tee_attested", "attestation_id", "model"}
L0_GROUPS = {"actor", "action", "object", "context", "linkage"}
REASON_SOURCES = {"rule", "shap", "graph", "attention"}


def test_backend_md_defines_the_alert_contract():
    """The contract doc itself must enumerate every L6 alert key (no missing field)."""
    bm = _read("BACKEND.md")
    missing = [k for k in L6_ALERT_KEYS if f'"{k}"' not in bm]
    assert not missing, f"BACKEND.md §2 is missing alert keys: {missing}"


def test_ml_alert_matches_backend_md():
    """ml.base.interfaces.Alert.to_dict must emit exactly the BACKEND.md §2 alert keys."""
    src = _read("ml/base/interfaces.py")
    for k in L6_ALERT_KEYS:
        assert f'"{k}"' in src, f"ml Alert.to_dict missing contract key {k!r}"


def test_backend_alert_schema_matches_backend_md():
    """backend Alert pydantic model must declare every BACKEND.md §2 alert key."""
    src = _read("backend/services/api/app/schemas/alerts.py")
    for k in L6_ALERT_KEYS:
        assert re.search(
            rf"\b{k}\b", src
        ), f"backend Alert schema missing contract key {k!r}"


def test_reason_code_shape_agrees_across_ml_and_backend():
    """reason_codes source enum {rule,shap,graph,attention} must match in ml + backend + BACKEND.md."""
    ml_src = _read("ml/base/interfaces.py")
    be_src = _read("backend/services/api/app/schemas/common.py") + _read(
        "backend/services/api/app/schemas/alerts.py"
    )
    bm = _read("BACKEND.md")
    for s in REASON_SOURCES:
        assert f'"{s}"' in ml_src, f"ml ReasonCode missing source {s!r}"
        assert s in be_src, f"backend ReasonSource missing {s!r}"
        assert s in bm, f"BACKEND.md missing reason source {s!r}"


def test_narrate_response_shape_agrees():
    """narrate() response keys must match BACKEND.md §7 in ml gateway + backend narrative route."""
    gw = _read("ml/narrative/gateway.py")
    bm = _read("BACKEND.md")
    for k in NARRATE_KEYS:
        assert f'"{k}"' in gw, f"ml narrate() response missing key {k!r}"
        assert k in bm, f"BACKEND.md §7 missing narrate key {k!r}"


def test_l0_event_groups_agree_across_data_and_backend_md():
    """The L0 event's 5 field groups must match in DATA's schema + BACKEND.md §1."""
    data_src = _read("data/schemas/l0_event.py")
    bm = _read("BACKEND.md")
    for g in L0_GROUPS:
        assert g in data_src, f"DATA L0 schema missing group {g!r}"
        assert g in bm, f"BACKEND.md §1 missing L0 group {g!r}"


def test_pii_tokenized_is_always_true_on_egress_contract():
    """pii_tokenized must default True in both alert schemas (raw PII never on egress)."""
    assert re.search(
        r"pii_tokenized.*=.*True|pii_tokenized.*True", _read("ml/base/interfaces.py")
    )
    assert re.search(
        r"pii_tokenized.*True", _read("backend/services/api/app/schemas/alerts.py")
    )
