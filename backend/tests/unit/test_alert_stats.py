"""Dashboard portfolio counts (GET /alerts/stats) — computed server-side over RBAC-visible alerts so
the header cards read at true scale (hundreds), not a single page."""

from __future__ import annotations


def test_alert_stats_requires_auth(client):
    assert client.get("/api/v1/alerts/stats").status_code == 401


def test_alert_stats_shape_base(client, auth):
    # Bulk seeding is off in tests → just the curated demo alerts; verify the contract + arithmetic.
    r = client.get("/api/v1/alerts/stats", headers=auth("lead"))
    assert r.status_code == 200
    s = r.json()
    for k in ("total", "open", "high_critical", "sla_at_risk", "confirmed_fraud", "open_exposure_inr"):
        assert k in s and isinstance(s[k], int)
    assert s["open"] <= s["total"]
    assert s["high_critical"] <= s["open"]
    assert s["confirmed_fraud"] >= 1  # alr_demo04


def test_alert_stats_reads_hundreds_with_bulk(client, auth):
    # Enable the bulk demo population (as the running console/deploy does) and confirm the cards
    # read in the hundreds — the stakeholder-visible behaviour.
    from app.store.seed import _seed_bulk_alerts

    _seed_bulk_alerts()
    s = client.get("/api/v1/alerts/stats", headers=auth("lead")).json()
    assert s["open"] >= 200
    assert s["high_critical"] >= 100
    assert s["sla_at_risk"] >= 30
    # bulk alerts are never confirmed_fraud → regulatory figures stay driven by curated cases only
    assert s["confirmed_fraud"] == 1
