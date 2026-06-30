"""Graceful degradation (BACKEND-15): serving down → L1-rules-only + mark for re-score."""

from __future__ import annotations

from app.clients.feature_client import FeatureReader
from app.pipeline.online import OnlinePipeline
from app.store.alert_store import AlertStore
from reliability.degradation import DEGRADATION


def _soft_event():
    return {
        "event_id": "evt_degrade_1",
        "ts": "2026-06-30T02:33:10Z",
        "actor": {"employee_id": "EMP-7f3a"},
        "action": {"verb": "login", "channel": "iam"},
        "object": {},
        "context": {"is_off_hours": True},  # off-hours soft rule fires
        "linkage": {},
    }


def test_degrades_to_l1_only_when_serving_unavailable():
    p = OnlinePipeline(feature_reader=FeatureReader(), store=AlertStore())
    alert = p.process(_soft_event(), force_degraded=True)  # simulate model server down
    assert alert is not None, "must still emit via L1 rules (never go dark)"
    assert alert.contributing_layers == ["L1_rules"]
    assert alert.model_versions == {"degraded": "L1_rules_only"}
    assert DEGRADATION.degraded is True
    assert "evt_degrade_1" in DEGRADATION.pending_rescore()


def test_no_alert_when_degraded_and_no_rule_fires():
    p = OnlinePipeline(feature_reader=FeatureReader(), store=AlertStore())
    benign = {
        "event_id": "evt_degrade_2",
        "ts": "2026-06-30T12:00:00Z",
        "actor": {"employee_id": "EMP-7f3a"},
        "action": {"verb": "view_dashboard"},
        "object": {},
        "context": {"is_off_hours": False},
        "linkage": {},
    }
    alert = p.process(benign, force_degraded=True)
    assert alert is None  # nothing fired; event marked for re-score, no alert fabricated
    assert "evt_degrade_2" in DEGRADATION.pending_rescore()
