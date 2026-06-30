"""24.5(d) worked-burst end-to-end (BACKEND-13): create_beneficiary → approve_payment → alert."""

from __future__ import annotations

from app.clients.feature_client import FeatureReader
from app.pipeline.online import OnlinePipeline
from app.store.alert_store import AlertStore


def _pipeline() -> OnlinePipeline:
    # Fresh feature reader + store so the burst correlates in isolation; full fusion (no short-circuit)
    # so the alert carries SHAP + L2/L3 layers exactly like Part 24.5b.
    return OnlinePipeline(feature_reader=FeatureReader(), store=AlertStore(), short_circuit=False)


def _create_event():
    return {
        "event_id": "evt_burst_create",
        "ts": "2026-06-30T02:14:07Z",
        "actor": {"employee_id": "EMP-7f3a", "role": "ops_maker", "peer_group": "PG-ops-tf"},
        "action": {"verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker"},
        "object": {"beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": None},
        "context": {"is_off_hours": True},
        "linkage": {},
    }


def _approve_event():
    return {
        "event_id": "evt_burst_approve",
        "ts": "2026-06-30T02:33:10Z",
        "actor": {"employee_id": "EMP-7f3a", "role": "ops_maker", "peer_group": "PG-ops-tf"},
        "action": {"verb": "approve_payment", "channel": "cbs"},
        "object": {"beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": 4_800_000},
        "context": {"is_off_hours": True},
        "linkage": {},
    }


def test_worked_burst_emits_high_alert_with_reason_codes():
    p = _pipeline()
    create_alert = p.process_full(_create_event())  # off-hours only → below threshold, no alert
    assert create_alert is None

    alert = p.process_full(_approve_event())
    assert alert is not None, "the burst must produce an alert"
    assert alert.entity_id == "EMP-7f3a"
    assert alert.severity == "high"
    assert alert.risk_score >= 70
    assert alert.exposure_inr == 4_800_000
    assert alert.pii_tokenized is True
    assert alert.sla_due_ts is not None

    codes = {rc.code for rc in alert.reason_codes if rc.code}
    sources = {rc.source for rc in alert.reason_codes}
    assert "NEW_BENEFICIARY_THEN_HIGHVALUE" in codes  # rule provenance
    assert "shap" in sources  # SHAP top features assembled
    assert "L1_rules" in alert.contributing_layers
    assert "L3_gbdt" in alert.contributing_layers
    # model_version recorded for reproducibility
    assert alert.model_versions.get("L3_gbdt")


def test_burst_alert_lands_in_store_once():
    p = _pipeline()
    p.process_full(_create_event())
    p.process_full(_approve_event())
    high = [a for a in p.store.all() if a.severity == "high"]
    assert len(high) == 1
