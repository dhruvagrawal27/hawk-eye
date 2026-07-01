"""Phase 4 — Sub-threshold ('hidden 95%') activity. Everything scored under the 70 emit line is
recorded-not-alerted; this surface makes the detection funnel + near-miss watchlist visible."""

from __future__ import annotations


def test_sub_threshold_requires_auth(client):
    assert client.get("/api/v1/activity/sub-threshold").status_code == 401


def test_sub_threshold_funnel_and_watchlist(client, auth):
    r = client.get("/api/v1/activity/sub-threshold", headers=auth("analyst"))
    assert r.status_code == 200
    body = r.json()

    assert body["emit_threshold"] == 70
    # funnel integrity: sub_threshold == sum of band counts, and scored == alerted + sub_threshold
    assert body["sub_threshold"] == sum(b["count"] for b in body["bands"])
    assert body["total_scored"] == body["alerted"] + body["sub_threshold"]
    assert body["alerted"] >= 1
    # the silent majority: sub-threshold dwarfs what surfaces as alerts
    assert body["sub_threshold"] > body["alerted"]

    # the watchlist is the near-miss population: elevated-but-not-alerted (40–69, under the 70 bar)
    assert body["watchlist"], "expected a seeded near-miss watchlist"
    for item in body["watchlist"]:
        assert 40 <= item["score"] < 70
        assert item["entity_id"] and item["top_signal"]
    # ranked high→low (near-misses first) + deduped per entity
    scores = [i["score"] for i in body["watchlist"]]
    assert scores == sorted(scores, reverse=True)
    assert len({i["entity_id"] for i in body["watchlist"]}) == len(body["watchlist"])
