"""Health + metrics contract (BACKEND-1)."""

from __future__ import annotations


def test_health_shape(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "hawk-eye-api"
    assert body["alert_only"] is True  # invariant
    assert "mtls_internal" in body
    assert "pii" in body


def test_metrics_prometheus_exposition(client):
    # touch a route so a counter is non-empty
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "version=0.0.4" in r.headers["content-type"]
    assert "hawkeye_http_requests_total" in r.text


def test_all_routes_under_api_v1(client):
    spec = client.get("/api/v1/openapi.json").json()
    ops_routes = ("/health", "/metrics", "/readyz", "/api/readyz")
    non_ops = [p for p in spec["paths"] if p not in ops_routes]
    assert non_ops, "expected API routes"
    assert all(p.startswith("/api/v1") for p in non_ops), non_ops
