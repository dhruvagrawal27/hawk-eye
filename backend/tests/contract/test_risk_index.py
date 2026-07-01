"""M2.1 — GET /entities/{id}/risk-index contract: RBAC, shape, audit, 404."""

from __future__ import annotations


def test_risk_index_requires_view_alerts(client, auth):
    assert client.get("/api/v1/entities/EMP-7f3a/risk-index").status_code == 401
    # service account (write-only scope) lacks VIEW_ALERTS
    assert client.get("/api/v1/entities/EMP-7f3a/risk-index", headers=auth("service")).status_code == 403


def test_risk_index_shape_and_audit(client, auth):
    r = client.get("/api/v1/entities/EMP-7f3a/risk-index", headers=auth("analyst"))
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["composite"] <= 100
    for k in ("hr_score", "access_score", "anomaly_score"):
        assert 0.0 <= body[k] <= 1.0
    assert body["components"] and body["top_drivers"]
    assert body["calibrated"] is False  # stub weights — human review only

    from app.audit.writer import AUDIT

    assert any(e.action == "entity.risk-index" and e.target == "EMP-7f3a" for e in AUDIT.all())


def test_risk_index_unknown_entity_404(client, auth):
    assert client.get("/api/v1/entities/EMP-nope/risk-index", headers=auth("analyst")).status_code == 404
