"""L1 rules engine unit tests (BACKEND-5): firing, versioning, hot-reload, cold start."""

from __future__ import annotations

import shutil

import pytest

from rules_engine.engine import DEFAULT_ENGINE, RulesEngine
from rules_engine.loader import RULES_DIR


def _ev(verb, *, amount=0, off=False, channel="cbs", app_txn=True, actor="EMP-7f3a", **obj):
    return {
        "event_id": "evt_x",
        "actor": {"employee_id": actor, "privileged_flag": False},
        "action": {"verb": verb, "channel": channel, "maker_checker": obj.pop("mc", None)},
        "object": {"amount": amount, **obj},
        "context": {"is_off_hours": off},
        "linkage": {"app_txn_id": "app1" if app_txn else None},
    }


def test_new_beneficiary_highvalue_hard_hit():
    ev = _ev("approve_payment", amount=4_800_000, off=True, beneficiary_id="BEN-9b1c")
    res = DEFAULT_ENGINE.evaluate(ev, {"minutes_since_new_beneficiary": 19})
    assert "NEW_BENEFICIARY_THEN_HIGHVALUE" in res.fired_codes
    assert res.hard_hit and res.severity == "high"


def test_off_hours_only_is_soft():
    res = DEFAULT_ENGINE.evaluate(_ev("login", off=True), {})
    assert "OFF_HOURS_ACTIVITY" in res.fired_codes
    assert not res.hard_hit


def test_db_write_without_app_txn_hard_hit():
    res = DEFAULT_ENGINE.evaluate(_ev("db_write", channel="db", app_txn=False), {})
    assert "DB_WRITE_WITHOUT_APP_TXN" in res.fired_codes
    assert res.hard_hit


def test_entitlement_self_grant():
    ev = _ev("grant_entitlement", target_employee_id="EMP-7f3a", entitlement="admin")
    res = DEFAULT_ENGINE.evaluate(ev, {})
    assert "ENTITLEMENT_SELF_GRANT" in res.fired_codes


def test_just_under_threshold():
    res = DEFAULT_ENGINE.evaluate(_ev("payment", amount=9_80_000), {})
    assert "JUST_UNDER_THRESHOLD" in res.fired_codes


def test_cold_start_no_features_no_labels():
    # Rules work with zero online features and zero labels (deterministic Layer 1).
    res = DEFAULT_ENGINE.evaluate(_ev("login", off=True))
    assert res.fired  # off-hours still fires; no ML / labels involved


def test_every_rule_is_versioned():
    for cfg in DEFAULT_ENGINE.list_rules():
        assert cfg.version and cfg.version.count(".") >= 1


def test_hot_reload_picks_up_changes(tmp_path):
    rules_dir = tmp_path / "rules"
    shutil.copytree(RULES_DIR, rules_dir)
    engine = RulesEngine(rules_dir=rules_dir)
    assert engine.evaluate(_ev("login", off=True)).fired  # off-hours enabled

    # Disable OFF_HOURS_ACTIVITY by rewriting it to its own file, then hot-reload.
    (rules_dir / "off_hours_activity.yaml").write_text(
        "code: OFF_HOURS_ACTIVITY\nname: off\nenabled: false\nseverity: medium\n"
        "hard_hit: false\nversion: 2.0.0\nparams: {}\n",
        encoding="utf-8",
    )
    assert engine.maybe_reload() is True
    assert "OFF_HOURS_ACTIVITY" not in engine.evaluate(_ev("login", off=True)).fired_codes


def test_disable_via_upsert_stops_firing():
    engine = RulesEngine()
    cfg = engine.get_rule("JUST_UNDER_THRESHOLD")
    disabled = type(cfg)(**{**cfg.__dict__, "enabled": False})
    engine.upsert_rule(disabled, persist=False)
    res = engine.evaluate(_ev("payment", amount=9_80_000))
    assert "JUST_UNDER_THRESHOLD" not in res.fired_codes


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
