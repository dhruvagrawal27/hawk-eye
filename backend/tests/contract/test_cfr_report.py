"""GET /reports/cfr contract (M1.3): RBAC, SCAFFOLD flag, confirmed-fraud feed + audit."""

from __future__ import annotations


def test_cfr_requires_compliance_role(client, auth):
    assert client.get("/api/v1/reports/cfr").status_code == 401  # no JWT
    assert client.get("/api/v1/reports/cfr", headers=auth("analyst")).status_code == 403


def test_cfr_shape_and_scaffold_flag(client, auth):
    # The demo seed already contains at least one human-confirmed fraud; the feed reflects it.
    r = client.get("/api/v1/reports/cfr", headers=auth("compliance"))
    assert r.status_code == 200
    body = r.json()
    assert body["submission_enabled"] is False  # SCAFFOLD: live CFR channel absent
    assert body["count"] == len(body["items"])
    assert body["dami_summary"]["total_cases"] == body["count"]
    for item in body["items"]:
        assert item["cfr_id"].startswith("cfr_") and item["entity_id"]


def test_cfr_lists_human_confirmed_fraud_and_audits(client, auth):
    # Alert-only: a CFR entry exists only after a HUMAN confirms fraud (AGM Vigilance).
    d = client.post(
        "/api/v1/alerts/alr_demo01/disposition",
        headers=auth("lead"),
        json={"outcome": "fraud", "notes": "confirmed", "evidence_ids": []},
    )
    assert d.status_code == 200 and d.json()["status"] == "confirmed_fraud"

    r = client.get("/api/v1/reports/cfr", headers=auth("compliance"))
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    item = body["items"][0]
    assert item["cfr_id"].startswith("cfr_") and item["entity_id"]
    assert body["dami_summary"]["total_cases"] == body["count"]

    from app.audit.writer import AUDIT

    assert any(e.action == "report.cfr" for e in AUDIT.all())
