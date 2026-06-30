"""Idempotency / exactly-once (BACKEND-14): replaying an event_id must not double-alert."""

from __future__ import annotations

from app.clients.feature_client import FeatureReader
from app.pipeline.online import OnlinePipeline
from app.store.alert_store import AlertStore


def _hard_event():
    return {
        "event_id": "evt_replay_1",
        "ts": "2026-06-30T02:33:10Z",
        "actor": {"employee_id": "EMP-7f3a"},
        "action": {"verb": "db_write", "channel": "db"},
        "object": {"account_id": "ACCT-1"},
        "context": {"is_off_hours": True},
        "linkage": {"app_txn_id": None},  # DB write without app txn → hard hit
    }


def test_replay_does_not_double_alert():
    p = OnlinePipeline(feature_reader=FeatureReader(), store=AlertStore())
    first = p.process(_hard_event())
    replay = p.process(_hard_event())  # same event_id
    assert first is not None
    assert replay is None, "replayed event_id must not produce a second alert"
    assert len(p.store.all()) == 1
