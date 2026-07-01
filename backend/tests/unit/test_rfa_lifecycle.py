"""M2.5 — RFA lifecycle state machine + 6-month clock + natural-justice gate (unit)."""

from __future__ import annotations

import pytest

from regulatory.rfa_lifecycle import RfaLifecycleService, RfaTransitionError
from regulatory.util import add_days

TS = "2026-01-01T00:00:00Z"


def _svc() -> RfaLifecycleService:
    return RfaLifecycleService()


def test_trigger_sets_180d_clock_and_show_cause():
    s = _svc()
    e = s.trigger("EMP-1", triggered_ts=TS, alert_id="alr_1", triggers=["SWIFT_CBS_MISMATCH"])
    assert e.state == "triggered"
    assert e.examination_due_ts == add_days(TS, 180)
    assert e.show_cause_due_ts == add_days(TS, 30)
    assert s.is_rfa_triggered("EMP-1")


def test_trigger_idempotent_per_entity():
    s = _svc()
    assert s.trigger("E", triggered_ts=TS) is s.trigger("E", triggered_ts=TS)


def test_confirm_requires_show_cause_response():
    s = _svc()
    s.trigger("E", triggered_ts=TS)
    s.open_examination("E")
    with pytest.raises(RfaTransitionError):
        s.close("E", outcome="confirmed", now_ts=add_days(TS, 10))  # natural-justice gate
    s.record_show_cause_response("E", response_ts=add_days(TS, 5))
    e = s.close("E", outcome="confirmed", now_ts=add_days(TS, 10))
    assert e.state == "closed" and e.outcome == "confirmed"


def test_exonerate_closes_without_show_cause():
    s = _svc()
    s.trigger("E", triggered_ts=TS)
    s.open_examination("E")
    e = s.close("E", outcome="exonerated", now_ts=add_days(TS, 5))
    assert e.state == "closed" and e.outcome == "exonerated"


def test_illegal_show_cause_before_examination():
    s = _svc()
    s.trigger("E", triggered_ts=TS)
    with pytest.raises(RfaTransitionError):
        s.record_show_cause_response("E", response_ts=TS)


def test_window_expiry_nudge():
    s = _svc()
    s.trigger("E", triggered_ts=TS)
    s.open_examination("E")
    assert not s.check_window_expiry(add_days(TS, 100))
    assert any(e.entity_id == "E" for e in s.check_window_expiry(add_days(TS, 200)))


def test_missing_examination_raises():
    with pytest.raises(RfaTransitionError):
        _svc().open_examination("nope")
