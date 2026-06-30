"""SoD / toxic-combination matrix unit tests (BACKEND-6)."""

from __future__ import annotations

from rules_engine.context import RuleContext
from rules_engine.sod_matrix import SoDMatrix


def _ctx(features=None, **event):
    base = {"actor": {"employee_id": "EMP-7f3a"}, "action": {}, "object": {}}
    base.update(event)
    return RuleContext(event=base, features=features or {})


def test_maker_checker_same_actor_flagged():
    res = SoDMatrix().score(_ctx({"maker_checker_same_actor": True}))
    assert any(f.code == "SOD_MAKER_CHECKER_SAME_ACTOR" for f in res.flags)
    assert res.score >= 0.9


def test_isolated_pair_flagged():
    res = SoDMatrix().score(
        _ctx({"maker_checker_pair_isolated": True, "maker_checker_partner": "EMP-1a09"})
    )
    assert any(f.code == "SOD_CREATE_APPROVE_ISOLATED_PAIR" for f in res.flags)


def test_self_grant_flagged():
    res = SoDMatrix().score(
        _ctx(object={"target_employee_id": "EMP-7f3a"}, actor={"employee_id": "EMP-7f3a"})
    )
    assert any(f.code == "SOD_SELF_GRANT_ENTITLEMENT" for f in res.flags)


def test_toxic_entitlement_combination():
    res = SoDMatrix().score(_ctx({"held_entitlements": ["create_beneficiary", "approve_payment"]}))
    assert any(f.code == "SOD_TOXIC_ENTITLEMENT_COMBINATION" for f in res.flags)


def test_no_flags_when_clean():
    res = SoDMatrix().score(_ctx({"held_entitlements": ["read_only"]}))
    assert not res.fired


def test_configurable_conflicts():
    custom = SoDMatrix(conflicts=[frozenset({"a", "b"})])
    res = custom.score(_ctx({"held_entitlements": ["a", "b"]}))
    assert any(f.code == "SOD_TOXIC_ENTITLEMENT_COMBINATION" for f in res.flags)
