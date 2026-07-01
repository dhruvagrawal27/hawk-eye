"""M2.5 — RFA lifecycle routes: disposition triggers RFA, RBAC, natural-justice gate, audit."""

from __future__ import annotations


def _entity_of(client, auth, alert_id: str) -> str:
    return client.get(f"/api/v1/alerts/{alert_id}", headers=auth("analyst")).json()["entity_id"]


def test_fraud_disposition_triggers_rfa_and_full_lifecycle(client, auth):
    # A human 'fraud' disposition opens the RFA examination (alert-only).
    d = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("lead"),
        json={"outcome": "fraud", "notes": "confirmed", "evidence_ids": []},
    )
    assert d.status_code == 200
    entity = _entity_of(client, auth, "alr_demo01")

    # RBAC: an RM cannot see/drive RFA; Compliance can.
    assert client.get(f"/api/v1/rfa/{entity}", headers=auth("analyst")).status_code == 403
    r = client.get(f"/api/v1/rfa/{entity}", headers=auth("compliance"))
    assert r.status_code == 200 and r.json()["state"] == "triggered"
    assert r.json()["examination_due_ts"] and r.json()["show_cause_due_ts"]

    # Open the examination.
    ex = client.post(f"/api/v1/rfa/{entity}/examination", headers=auth("compliance"))
    assert ex.status_code == 200 and ex.json()["state"] == "under_examination"

    # Natural justice: cannot confirm before a show-cause response → 409.
    early = client.post(
        f"/api/v1/rfa/{entity}/close", headers=auth("compliance"), json={"outcome": "confirmed"}
    )
    assert early.status_code == 409

    # Record show-cause, then confirm-close.
    assert client.post(f"/api/v1/rfa/{entity}/show-cause", headers=auth("compliance")).status_code == 200
    ok = client.post(
        f"/api/v1/rfa/{entity}/close", headers=auth("compliance"), json={"outcome": "confirmed"}
    )
    assert ok.status_code == 200 and ok.json()["state"] == "closed" and ok.json()["outcome"] == "confirmed"

    from app.audit.writer import AUDIT

    actions = {e.action for e in AUDIT.all()}
    assert {"rfa.examination.open", "rfa.show_cause.response", "rfa.close"} <= actions


def test_rfa_unknown_entity_404(client, auth):
    assert client.get("/api/v1/rfa/EMP-none", headers=auth("compliance")).status_code == 404
