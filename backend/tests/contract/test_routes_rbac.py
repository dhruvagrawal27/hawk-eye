"""Route-level RBAC + auth contract (BACKEND-2/3/8/21/22)."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/alerts"),
        ("get", "/api/v1/alerts/alr_demo01"),
        ("get", "/api/v1/entities/EMP-7f3a"),
        ("get", "/api/v1/explanations/alr_demo01"),
        ("get", "/api/v1/rules"),
        ("get", "/api/v1/models"),
        ("get", "/api/v1/audit"),
        ("get", "/api/v1/admin/users"),
        ("get", "/api/v1/reports/fmr"),
    ],
)
def test_protected_routes_401_without_jwt(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_invalid_token_401(client):
    assert (
        client.get("/api/v1/alerts", headers={"Authorization": "Bearer not.a.jwt"}).status_code
        == 401
    )


def test_service_account_scoped_token_denied_human_reads(client, auth):
    # Service accounts use scoped tokens (Part 24.1: scoped_token / write_only) — their token scope
    # is audit:write/events:write, so they cannot READ the audit trail or the alert queue.
    h = auth("service")
    assert client.get("/api/v1/audit", headers=h).status_code == 403  # write-only, no read
    assert (
        client.get("/api/v1/alerts", headers=h).status_code == 403
    )  # scoped token lacks view_alerts


def test_analyst_denied_audit_and_rules(client, auth):
    h = auth("analyst")
    assert client.get("/api/v1/audit", headers=h).status_code == 403
    assert client.get("/api/v1/rules", headers=h).status_code == 403


def test_auditor_can_view_audit(client, auth):
    r = client.get("/api/v1/audit", headers=auth("auditor"))
    assert r.status_code == 200
    assert "items" in r.json()


def test_admin_only_users(client, auth):
    assert client.get("/api/v1/admin/users", headers=auth("admin")).status_code == 200
    assert client.get("/api/v1/admin/users", headers=auth("analyst")).status_code == 403


def test_unmask_audited_and_analyst_needs_justification(client, auth):
    # Analyst unmask without justification → 403 (case-scoped, logged).
    r = client.post(
        "/api/v1/entities/EMP-7f3a/unmask", headers=auth("analyst"), json={"tokens": []}
    )
    assert r.status_code == 403
    # Senior unmask → 200 and writes a pii.unmask audit event.
    r2 = client.post(
        "/api/v1/entities/EMP-7f3a/unmask",
        headers=auth("senior"),
        json={"tokens": [], "justification": "case review"},
    )
    assert r2.status_code == 200 and r2.json()["audit_id"].startswith("aud_")
    from app.audit.writer import AUDIT

    assert any(e.action == "pii.unmask" for e in AUDIT.all())


def test_who_viewed_whom_audited(client, auth):
    client.get("/api/v1/alerts/alr_demo01", headers=auth("senior"))
    from app.audit.writer import AUDIT

    views = [e for e in AUDIT.all() if e.action == "alert.view" and e.target == "EMP-7f3a"]
    assert views, "alert view must be audited (who-viewed-whom)"


def test_four_eyes_rule_change(client, auth):
    # Compliance proposes; the SAME person cannot approve (four-eyes); a SECOND Compliance can.
    prop = client.post(
        "/api/v1/rules",
        headers=auth("compliance"),
        json={"code": "OFF_HOURS_ACTIVITY", "change_reason": "tighten", "enabled": True},
    )
    assert prop.status_code == 201
    change_id = prop.json()["change_id"]
    self_approve = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("compliance"),
        json={"change_id": change_id, "approve": True},
    )
    assert self_approve.status_code == 403  # four-eyes: proposer ≠ approver
    co2_approve = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("compliance2"),
        json={"change_id": change_id, "approve": True},
    )
    assert co2_approve.status_code == 200
    assert co2_approve.json()["status"] == "approved"
    assert co2_approve.json()["new_version"]


def test_team_lead_can_propose_but_not_approve_rules(client, auth):
    # Team Lead = ⚠️ propose-only (Part 24.1); Compliance = change-controlled approver.
    prop = client.post(
        "/api/v1/rules",
        headers=auth("lead"),
        json={"code": "OFF_HOURS_ACTIVITY", "change_reason": "tighten", "enabled": True},
    )
    assert prop.status_code == 201  # Lead may propose
    change_id = prop.json()["change_id"]
    lead_approve = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("lead"),
        json={"change_id": change_id, "approve": True},
    )
    assert lead_approve.status_code == 403  # Lead may NOT approve
    co_approve = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("compliance"),
        json={"change_id": change_id, "approve": True},
    )
    assert co_approve.status_code == 200


def test_put_rules_proposes_update_four_eyes(client, auth):
    # PUT /rules/{code} (Part 24.2) proposes an update; approval is Compliance + four-eyes.
    r = client.put(
        "/api/v1/rules/JUST_UNDER_THRESHOLD",
        headers=auth("compliance"),
        json={
            "code": "JUST_UNDER_THRESHOLD",
            "change_reason": "widen band",
            "params": {"band": 0.1},
        },
    )
    assert r.status_code == 201
    change_id = r.json()["change_id"]
    ok = client.post(
        f"/api/v1/rules/{change_id}/approve",
        headers=auth("compliance2"),
        json={"change_id": change_id, "approve": True},
    )
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    # unknown rule → 404
    assert (
        client.put(
            "/api/v1/rules/NOPE",
            headers=auth("compliance"),
            json={"code": "NOPE", "change_reason": "x"},
        ).status_code
        == 404
    )


def test_view_audit_view_own_scope(client, auth):
    # Senior Investigator + Model Engineer have VIEW_AUDIT = ⚠️ view-own: they only see their own
    # actions, never another user's audit entries. Auditor sees the full trail.
    client.get("/api/v1/alerts/alr_demo01", headers=auth("senior"))  # senior makes an audited view
    sr = client.get("/api/v1/audit", headers=auth("senior")).json()
    assert sr["items"], "senior should see their own audit entries"
    assert all(e["actor"] == "EMP-sr01" for e in sr["items"]), "view-own must filter to self"
    full = client.get("/api/v1/audit", headers=auth("auditor")).json()
    actors = {e["actor"] for e in full["items"]}
    assert len(actors) >= 1  # auditor sees everyone's actions (unfiltered)


def test_disposition_override_requires_team_lead(client, auth):
    # First disposition by analyst (alert is open) succeeds.
    r1 = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("analyst"),
        json={"outcome": "false_positive", "notes": "", "evidence_ids": []},
    )
    assert r1.status_code == 200
    # Re-dispositioning an already-dispositioned alert is an OVERRIDE → Senior is denied, Lead allowed.
    r2 = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("senior"),
        json={"outcome": "fraud", "notes": "reopen", "evidence_ids": []},
    )
    assert r2.status_code == 403
    r3 = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("lead"),
        json={"outcome": "fraud", "notes": "override", "evidence_ids": []},
    )
    assert r3.status_code == 200 and r3.json()["status"] == "confirmed_fraud"


def test_block_request_approve_is_team_lead_and_never_auto(client, auth):
    client.post(
        "/api/v1/alerts/alr_demo01/block-request",
        headers=auth("analyst"),
        json={"reason": "mule", "evidence_ids": []},
    )
    # Analyst cannot approve their own block request.
    assert (
        client.post(
            "/api/v1/alerts/alr_demo01/block-request/approve", headers=auth("analyst")
        ).status_code
        == 403
    )
    ok = client.post("/api/v1/alerts/alr_demo01/block-request/approve", headers=auth("lead"))
    assert ok.status_code == 200
    assert ok.json()["approved"] is True and ok.json()["auto_blocked"] is False


def test_platform_admin_cannot_promote_model(client, auth):
    r = client.post(
        "/api/v1/models/l3_catboost/promote?version=challenger-2026.06.30",
        headers=auth("admin"),
        json={"to_stage": "Production", "signoff_by": "EMP-me01", "canary_percent": 10},
    )
    assert r.status_code == 403  # deploy-infra-only, not model promotion


def test_model_promote_requires_distinct_signoff(client, auth):
    h = auth("model_engineer")
    same = client.post(
        "/api/v1/models/l3_catboost/promote?version=challenger-2026.06.30",
        headers=h,
        json={"to_stage": "Production", "signoff_by": "EMP-me01", "canary_percent": 10},
    )
    assert same.status_code == 403  # promoter ≠ approver
    ok = client.post(
        "/api/v1/models/l3_catboost/promote?version=challenger-2026.06.30",
        headers=h,
        json={"to_stage": "Production", "signoff_by": "EMP-tl01", "canary_percent": 10},
    )
    assert ok.status_code == 200 and ok.json()["signature_verified"] is True
