"""Privileged-session / entitlement rule unit tests (BACKEND-7)."""

from __future__ import annotations

from rules_engine.context import RuleContext
from rules_engine.privileged import (
    leaver_window_exfil,
    orphaned_account_use,
    privileged_session_correlation,
)
from rules_engine.rule import RuleConfig


def _cfg(code, **params):
    return RuleConfig(code=code, name=code, severity="high", params=params)


def _ctx(actor=None, action=None, features=None):
    return RuleContext(
        event={"actor": actor or {}, "action": action or {}, "object": {}, "context": {}},
        features=features or {},
    )


def test_privileged_session_correlation_fires():
    ctx = _ctx(actor={"employee_id": "EMP-3c55", "privileged_flag": True},
               action={"verb": "db_write", "channel": "db"})
    hit = privileged_session_correlation(ctx, _cfg("PRIVILEGED_SESSION_CORRELATION"))
    assert hit is not None and hit.code == "PRIVILEGED_SESSION_CORRELATION"


def test_orphaned_account_use_fires_for_leaver():
    ctx = _ctx(actor={"employee_id": "EMP-9f02", "leaver_flag": True}, action={"verb": "login"})
    assert orphaned_account_use(ctx, _cfg("ORPHANED_ACCOUNT_USE")) is not None


def test_leaver_window_exfil_requires_volume():
    cfg = _cfg("LEAVER_WINDOW_EXFIL", exfil_verbs=["export"], export_volume_min=1000)
    ctx = _ctx(actor={"employee_id": "EMP-9f02", "leaver_flag": True}, action={"verb": "export"},
               features={"export_record_count": 5000})
    assert leaver_window_exfil(ctx, cfg) is not None
    ctx_low = _ctx(actor={"employee_id": "EMP-9f02", "leaver_flag": True}, action={"verb": "export"},
                   features={"export_record_count": 10})
    assert leaver_window_exfil(ctx_low, cfg) is None
