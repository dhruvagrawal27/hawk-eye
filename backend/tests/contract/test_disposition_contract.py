"""Disposition + block-request contract (BACKEND-20, blueprint Part 24.5c). Alert-only invariants."""

from __future__ import annotations


def test_disposition_exact_response(client, auth):
    r = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("analyst"),
        json={"outcome": "fraud", "notes": "Confirmed shell beneficiary.", "evidence_ids": ["evt_8f2a1c90"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"alert_id", "status", "label_written", "feedback_queued_for_retraining", "audit_id"}
    assert body["alert_id"] == "alr_demo01"
    assert body["status"] == "confirmed_fraud"
    assert body["label_written"] is True
    assert body["feedback_queued_for_retraining"] is True
    assert body["audit_id"].startswith("aud_")


def test_disposition_writes_label_and_audit(client, auth):
    client.post("/api/v1/alerts/alr_demo01/disposition", headers=auth("analyst"),
                json={"outcome": "fraud", "notes": "x", "evidence_ids": []})
    from app.store.alert_store import ALERTS
    assert ALERTS.get_disposition("alr_demo01") is not None
    assert any(rec["alert_id"] == "alr_demo01" for rec in ALERTS.feedback_queue())


def test_block_request_is_never_auto(client, auth):
    r = client.post("/api/v1/alerts/alr_demo01/block-request", headers=auth("analyst"),
                    json={"reason": "suspected mule", "evidence_ids": []})
    assert r.status_code == 200
    body = r.json()
    assert body["auto_blocked"] is False  # the system NEVER auto-blocks money
    assert body["requires_approval_by"] == "team_lead"  # Analyst→Lead approves
    assert body["status"] == "block_requested"


def test_compliance_cannot_disposition(client, auth):
    # SoD / RBAC: Compliance has no disposition capability (alert-only human-in-the-loop separation).
    r = client.post("/api/v1/alerts/alr_demo01/disposition", headers=auth("compliance"),
                    json={"outcome": "fraud", "notes": "", "evidence_ids": []})
    assert r.status_code == 403


def test_model_engineer_cannot_disposition_sod(client, auth):
    r = client.post("/api/v1/alerts/alr_demo01/disposition", headers=auth("model_engineer"),
                    json={"outcome": "fraud", "notes": "", "evidence_ids": []})
    assert r.status_code == 403  # deployer cannot label data / close alerts
