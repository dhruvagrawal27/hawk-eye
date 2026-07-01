"""L6.5 — action-gate PDP core + gate service (M3.1/M3.2/M3.3).

Covers the policy engine decisions + degradation, and the service e2e: HOLD→four-eyes (no
self-review), STEP_UP→challenge→retry-allows, idempotency, and the alert-only invariant
(object.amount is never gated; a hold's approval only PERMITS human execution).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agsvc.main import DECISIONS, HOLDS, STEP_UPS, app
from agsvc.policy_engine import ActionGate, Decision

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    DECISIONS.clear()
    STEP_UPS.clear()
    HOLDS.clear()
    yield


# ── policy engine (M3.1) ──────────────────────────────────────────────────────
def test_self_grant_holds():
    assert ActionGate().evaluate("self_grant").decision == Decision.HOLD_FOR_REVIEW


def test_swift_send_steps_up():
    assert ActionGate().evaluate("swift_send").decision == Decision.STEP_UP


def test_routine_verb_allows():
    assert ActionGate().evaluate("login").decision == Decision.ALLOW


def test_sod_over_threshold_forces_hold():
    assert (
        ActionGate().evaluate("db_write", sod_score=0.95).decision
        == Decision.HOLD_FOR_REVIEW
    )


def test_opa_deny_forces_hold():
    assert (
        ActionGate().evaluate("db_write", opa_deny=True).decision
        == Decision.HOLD_FOR_REVIEW
    )


def test_maker_checker_same_actor_holds_any_verb():
    r = ActionGate().evaluate("approve_payment", {"maker_checker_same_actor": True})
    assert r.decision == Decision.HOLD_FOR_REVIEW


def test_degradation_privileged_fails_closed():
    r = ActionGate().evaluate("db_write", governance_available=False, privileged=True)
    assert r.decision == Decision.HOLD_FOR_REVIEW and r.degraded


def test_degradation_routine_fails_open():
    r = ActionGate().evaluate("login", governance_available=False)
    assert r.decision == Decision.ALLOW and r.degraded


# ── service e2e (M3.2/M3.3) ───────────────────────────────────────────────────
def _event(verb, request_id, actor="EMP-x", priv=True, **kw):
    return {
        "actor": {"employee_id": actor, "role": "ops", "privileged_flag": priv},
        "action": {"verb": verb, "channel": "pam"},
        "object": kw.get("object", {}),
        "features": kw.get("features", {}),
        "request_id": request_id,
        "sod_score": kw.get("sod", 0.0),
    }


def test_hold_then_four_eyes_no_self_review():
    r = client.post(
        "/api/v1/actions/evaluate", json=_event("self_grant", "req-1")
    ).json()
    assert r["decision"] == "HOLD_FOR_REVIEW" and r["hold_id"]
    hid = r["hold_id"]
    # subject cannot resolve their own hold (four-eyes)
    self_rev = client.post(
        f"/api/v1/holds/{hid}/decision",
        json={"decider": "EMP-x", "approve": True, "justification": "self"},
    )
    assert self_rev.status_code == 403
    ok = client.post(
        f"/api/v1/holds/{hid}/decision",
        json={
            "decider": "EMP-boss",
            "approve": True,
            "justification": "reviewed & permitted",
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["status"] == "approved_via_four_eyes"
    assert (
        body["outcome"] == "permitted_for_human_initiated_execution"
    )  # NOT auto-executed


def test_step_up_then_retry_allows():
    r = client.post(
        "/api/v1/actions/evaluate", json=_event("swift_send", "req-2")
    ).json()
    assert r["decision"] == "STEP_UP" and r["challenge_id"]
    cid = r["challenge_id"]
    assert (
        client.post(
            f"/api/v1/step-ups/{cid}/challenge", json={"method": "mfa"}
        ).status_code
        == 200
    )
    retry = client.post(
        "/api/v1/actions/evaluate", json=_event("swift_send", "req-2")
    ).json()
    assert retry["decision"] == "ALLOW"


def test_idempotent_replay_returns_same_decision():
    a = client.post("/api/v1/actions/evaluate", json=_event("db_write", "req-3")).json()
    b = client.post("/api/v1/actions/evaluate", json=_event("db_write", "req-3")).json()
    assert a["action_id"] == b["action_id"] and a["decision"] == b["decision"]


def test_alert_only_amount_never_gated():
    # A huge object.amount must NOT change the decision — the gate has no money path.
    r = client.post(
        "/api/v1/actions/evaluate",
        json=_event("login", "req-4", object={"amount": 999_999_999}),
    ).json()
    assert r["decision"] == "ALLOW"


def test_manager_approval_requires_distinct_approver():
    r = client.post(
        "/api/v1/actions/evaluate", json=_event("swift_send", "req-5")
    ).json()
    cid = r["challenge_id"]
    bad = client.post(
        f"/api/v1/step-ups/{cid}/challenge",
        json={"method": "manager_approval", "approver": "EMP-x"},  # == actor
    )
    assert bad.status_code == 403


def test_health_declares_alert_only():
    h = client.get("/health").json()
    assert h["alert_only"] is True and h["gates_money"] is False
