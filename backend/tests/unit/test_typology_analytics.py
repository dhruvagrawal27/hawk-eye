"""Phase 5 — Management analytics. Fraud-typology prevalence + confirmed-rate: which insider
typologies actually fire, how often they're confirmed vs cleared, and the exposure behind them."""

from __future__ import annotations


def test_typology_analytics_requires_auth(client):
    assert client.get("/api/v1/analytics/typologies").status_code == 401


def test_typology_analytics_shape_and_totals(client, auth):
    r = client.get("/api/v1/analytics/typologies", headers=auth("lead"))
    assert r.status_code == 200
    body = r.json()

    tps = body["typologies"]
    assert len(tps) >= 10  # the insider typology catalogue
    # most-prevalent first
    counts = [t["alerts"] for t in tps]
    assert counts == sorted(counts, reverse=True)

    for t in tps:
        assert t["open"] == t["alerts"] - t["confirmed"] - t["false_positive"]
        denom = t["confirmed"] + t["false_positive"]
        if denom:
            assert abs(t["confirmed_rate"] - t["confirmed"] / denom) < 1e-3  # rounded to 4dp
        assert 0.0 <= t["confirmed_rate"] <= 1.0
        assert t["layers"], "each typology names the detection layers that catch it"

    totals = body["totals"]
    assert totals["alerts"] == sum(t["alerts"] for t in tps)
    assert totals["confirmed"] == sum(t["confirmed"] for t in tps)
    assert totals["exposure_inr"] == sum(t["exposure_inr"] for t in tps)
