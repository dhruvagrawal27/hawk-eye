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
    assert client.get("/api/v1/alerts", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


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
    r = client.post("/api/v1/entities/EMP-7f3a/unmask", headers=auth("analyst"), json={"tokens": []})
    assert r.status_code == 403
    # Senior unmask → 200 and writes a pii.unmask audit event.
    r2 = client.post("/api/v1/entities/EMP-7f3a/unmask", headers=auth("senior"),
                     json={"tokens": [], "justification": "case review"})
    assert r2.status_code == 200 and r2.json()["audit_id"].startswith("aud_")
    from app.audit.writer import AUDIT
    assert any(e.action == "pii.unmask" for e in AUDIT.all())


def test_who_viewed_whom_audited(client, auth):
    client.get("/api/v1/alerts/alr_demo01", headers=auth("senior"))
    from app.audit.writer import AUDIT
    views = [e for e in AUDIT.all() if e.action == "alert.view" and e.target == "EMP-7f3a"]
    assert views, "alert view must be audited (who-viewed-whom)"


def test_four_eyes_rule_change(client, auth):
    # Compliance proposes; the SAME person cannot approve (four-eyes); a Lead can.
    prop = client.post("/api/v1/rules", headers=auth("compliance"),
                       json={"code": "OFF_HOURS_ACTIVITY", "change_reason": "tighten", "enabled": True})
    assert prop.status_code == 201
    change_id = prop.json()["change_id"]
    self_approve = client.post(f"/api/v1/rules/{change_id}/approve", headers=auth("compliance"),
                               json={"change_id": change_id, "approve": True})
    assert self_approve.status_code == 403  # four-eyes: proposer ≠ approver
    lead_approve = client.post(f"/api/v1/rules/{change_id}/approve", headers=auth("lead"),
                               json={"change_id": change_id, "approve": True})
    assert lead_approve.status_code == 200
    assert lead_approve.json()["status"] == "approved"
    assert lead_approve.json()["new_version"]


def test_model_promote_requires_distinct_signoff(client, auth):
    h = auth("model_engineer")
    same = client.post("/api/v1/models/l3_catboost/promote?version=challenger-2026.06.30", headers=h,
                       json={"to_stage": "Production", "signoff_by": "EMP-me01", "canary_percent": 10})
    assert same.status_code == 403  # promoter ≠ approver
    ok = client.post("/api/v1/models/l3_catboost/promote?version=challenger-2026.06.30", headers=h,
                     json={"to_stage": "Production", "signoff_by": "EMP-tl01", "canary_percent": 10})
    assert ok.status_code == 200 and ok.json()["signature_verified"] is True
