"""Canonical audit-event envelope + hashing (DATABASE-5/6).

Single source of truth for the WORM audit record shape. The Avro producer schema
``infra/audit/kafka/audit_event.avsc`` mirrors this module field-for-field; the
contract test ``db/tests/test_audit_schema.py`` asserts they stay in sync.

Design notes
------------
* **Append-only / tamper-evident** (blueprint Part 8 l.311, Part 19.3 l.634):
  every record carries ``prev_hash`` (the previous sealed record's hash) and a
  ``record_hash = H(canonical_bytes(content) ‖ prev_hash)``. The WORM writer fills
  ``prev_hash``/``record_hash`` at seal time; producers leave them empty.
* **Canonical bytes** are deterministic JSON (sorted keys, tight separators, UTF-8)
  over the record *content* (everything except the two chaining fields). This makes
  the hash reproducible by any verifier in any language.
* **ALERT-ONLY** (golden rule 1): the audit trail records *human* decisions and
  *who-watched-whom*; it never encodes an automatic action.
* **Synthetic / tokenized only** (golden rule 2): ``pii_tokenized`` is always True;
  raw PII must never enter an audit record (BACKEND tokenizes before egress).
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from typing import Any, Dict, Mapping, Optional

SCHEMA_VERSION = "1.0.0"

# Fields excluded from the content hash (they are *about* the chain, not content).
_CHAIN_FIELDS = ("prev_hash", "record_hash")
_AUDIT_ID_RE = re.compile(r"^aud_[0-9a-zA-Z]{4,}$")
# Domain separator between the canonical content bytes and the prev_hash.
_HASH_SEP = b"\x00"


class AuditAction(str, Enum):
    """Every audited action class.

    Covers the six WORM record classes the blueprint requires (alerts,
    dispositions, model versions, feature snapshots, rule/threshold changes,
    investigators' own actions) plus registry access (Part 19.2) and the
    narrative audit memo (BACKEND.md §7).
    """

    # --- Investigators' own actions (watch-the-watchers, Part 19.3) ----------
    VIEW_ENTITY = "view_entity"  # who-viewed-whom (entity-360)
    VIEW_ALERT = "view_alert"  # who-viewed-whom (alert detail)
    # --- Alert / case workflow ----------------------------------------------
    ALERT_ASSIGN = "alert_assign"
    ALERT_CLOSE = "alert_close"
    ALERT_DISPOSITION = "alert_disposition"
    BLOCK_REQUEST = "block_request"
    BLOCK_REQUEST_APPROVE = "block_request_approve"
    # --- Rule / threshold change-control (four-eyes; BACKEND.md §6) ----------
    RULE_CHANGE = "rule_change"
    THRESHOLD_CHANGE = "threshold_change"
    # --- Model governance / registry (Part 19.2, Part 23) -------------------
    MODEL_VERSION_REGISTER = "model_version_register"
    MODEL_VERSION_PROMOTE = "model_version_promote"
    MODEL_VERSION_ARCHIVE = "model_version_archive"
    REGISTRY_READ = "registry_read"  # access logging (extraction-theft)
    REGISTRY_LOAD = "registry_load"  # signature-verified load
    # --- Feature store -------------------------------------------------------
    FEATURE_SNAPSHOT_WRITE = "feature_snapshot_write"
    # --- PII (separate, audited capability; BACKEND.md §3) ------------------
    PII_UNMASK = "pii_unmask"
    # --- Narrative LLM audit memo (BACKEND.md §7, Part 25) ------------------
    NARRATIVE_MEMO = "narrative_memo"
    # --- Admin / reporting ---------------------------------------------------
    USER_ADMIN = "user_admin"
    REPORT_EXPORT = "report_export"


class TargetType(str, Enum):
    """What an audit action points at."""

    ENTITY = "entity"
    ALERT = "alert"
    CASE = "case"
    RULE = "rule"
    MODEL = "model"
    FEATURE = "feature"
    REPORT = "report"
    NARRATIVE = "narrative"
    DISPOSITION = "disposition"
    USER = "user"


def build_envelope(
    *,
    audit_id: str,
    ts: str,
    actor_id: str,
    action: AuditAction | str,
    target_type: TargetType | str,
    target_id: str,
    actor_role: str = "",
    session_id: str = "",
    src_ip: str = "",
    details: Optional[Mapping[str, str]] = None,
    pii_tokenized: bool = True,
    prev_hash: str = "",
    record_hash: str = "",
) -> Dict[str, Any]:
    """Build a fully-formed audit envelope dict (matches the .avsc).

    Producers (BACKEND) call this with ``prev_hash``/``record_hash`` empty; the
    WORM writer fills them at seal time via :func:`compute_record_hash`.
    """
    action_v = action.value if isinstance(action, AuditAction) else str(action)
    target_v = (
        target_type.value if isinstance(target_type, TargetType) else str(target_type)
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_id": audit_id,
        "ts": ts,
        "actor": {
            "actor_id": actor_id,
            "role": actor_role,
            "session_id": session_id,
            "src_ip": src_ip,
        },
        "action": action_v,
        "target": {"type": target_v, "id": target_id},
        "details": {str(k): str(v) for k, v in (details or {}).items()},
        "pii_tokenized": bool(pii_tokenized),
        "prev_hash": prev_hash,
        "record_hash": record_hash,
    }


def canonical_bytes(record: Mapping[str, Any]) -> bytes:
    """Deterministic content bytes for hashing (excludes the chaining fields).

    Sorted keys + compact separators → reproducible across languages/runtimes.
    """
    content = {k: v for k, v in record.items() if k not in _CHAIN_FIELDS}
    return json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def compute_record_hash(record: Mapping[str, Any], prev_hash: str) -> str:
    """``record_hash = SHA-256( canonical_bytes(content) ‖ sep ‖ prev_hash )``."""
    h = hashlib.sha256()
    h.update(canonical_bytes(record))
    h.update(_HASH_SEP)
    h.update(prev_hash.encode("utf-8"))
    return h.hexdigest()


def validate_envelope(record: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` if a record violates the contract.

    Validates the structural shape, the action/target enums, the ``aud_*`` id
    convention, and the golden-rule invariant ``pii_tokenized is True``.
    """
    required = {
        "schema_version",
        "audit_id",
        "ts",
        "actor",
        "action",
        "target",
        "details",
        "pii_tokenized",
        "prev_hash",
        "record_hash",
    }
    missing = required - set(record.keys())
    if missing:
        raise ValueError(f"audit record missing fields: {sorted(missing)}")

    if not _AUDIT_ID_RE.match(str(record["audit_id"])):
        raise ValueError(f"audit_id must match aud_* : {record['audit_id']!r}")

    actor = record["actor"]
    if not isinstance(actor, Mapping) or "actor_id" not in actor:
        raise ValueError("actor must be a mapping with actor_id")

    target = record["target"]
    if not isinstance(target, Mapping) or {"type", "id"} - set(target.keys()):
        raise ValueError("target must be a mapping with type + id")

    try:
        AuditAction(str(record["action"]))
    except ValueError as exc:  # pragma: no cover - message clarity
        raise ValueError(f"unknown audit action: {record['action']!r}") from exc
    try:
        TargetType(str(target["type"]))
    except ValueError as exc:  # pragma: no cover - message clarity
        raise ValueError(f"unknown target type: {target['type']!r}") from exc

    if not isinstance(record["details"], Mapping):
        raise ValueError("details must be a map<string,string>")

    # Golden rule 2: raw PII must never be sealed. The trail is tokenized-only.
    if record["pii_tokenized"] is not True:
        raise ValueError("pii_tokenized must be True (synthetic/tokenized only)")
