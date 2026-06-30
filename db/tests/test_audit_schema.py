"""DATABASE-5/6 — audit envelope contract + canonical hashing."""

from __future__ import annotations

import pytest
from services.audit.audit_schema import (
    AuditAction,
    TargetType,
    build_envelope,
    canonical_bytes,
    compute_record_hash,
    validate_envelope,
)

REQUIRED_ACTIONS = {
    "view_entity",  # who-viewed-whom
    "view_alert",
    "alert_assign",
    "alert_close",
    "alert_disposition",
    "rule_change",  # rule/threshold change
    "threshold_change",
    "model_version_register",
    "model_version_promote",
    "registry_read",  # registry access (extraction-theft)
    "registry_load",
    "feature_snapshot_write",
    "pii_unmask",  # PII unmask
    "narrative_memo",  # narrative audit memo
}


def _envelope(**overrides):
    base = dict(
        audit_id="aud_abc123",
        ts="2026-06-30T02:41:55.000Z",
        actor_id="EMP-7f3a",
        action=AuditAction.VIEW_ENTITY,
        target_type=TargetType.ENTITY,
        target_id="EMP-1a09",
    )
    base.update(overrides)
    return build_envelope(**base)


def test_action_enum_covers_all_required_classes():
    have = {a.value for a in AuditAction}
    missing = REQUIRED_ACTIONS - have
    assert not missing, f"audit action enum missing: {missing}"


def test_validate_accepts_each_action_type():
    for action in AuditAction:
        rec = _envelope(action=action, target_type=TargetType.ALERT, target_id="alr_1")
        validate_envelope(rec)  # must not raise


def test_validate_rejects_bad_audit_id():
    with pytest.raises(ValueError):
        validate_envelope(_envelope(audit_id="bad-id"))


def test_validate_enforces_pii_tokenized_true():
    rec = _envelope()
    rec["pii_tokenized"] = False
    with pytest.raises(ValueError):
        validate_envelope(rec)


def test_canonical_bytes_excludes_chain_fields_and_is_deterministic():
    rec = _envelope(prev_hash="abc", record_hash="def")
    cb1 = canonical_bytes(rec)
    rec2 = _envelope(prev_hash="zzz", record_hash="yyy")  # different chain fields
    cb2 = canonical_bytes(rec2)
    assert cb1 == cb2, "canonical bytes must not depend on prev_hash/record_hash"
    assert b"prev_hash" not in cb1 and b"record_hash" not in cb1


def test_record_hash_changes_when_content_changes():
    a = _envelope()
    h1 = compute_record_hash(a, prev_hash="00")
    b = _envelope(target_id="EMP-DIFFERENT")
    h2 = compute_record_hash(b, prev_hash="00")
    assert h1 != h2


def test_narrative_memo_fields_carry_in_details():
    rec = _envelope(
        action=AuditAction.NARRATIVE_MEMO,
        target_type=TargetType.NARRATIVE,
        target_id="alr_3d7e22",
        details={
            "provider": "near_ai",
            "tee_attested": "true",
            "attestation_id": "att_1",
            "model": "gpt-oss-120b",
            "prompt_hash": "deadbeef",
        },
    )
    validate_envelope(rec)
    assert rec["details"]["provider"] == "near_ai"
