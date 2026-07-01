"""Deferred polish — per-layer score timeline. Mirrors ClickHouse `hawkeye.scores`: one series per
detection layer over time, so an investigator sees which layer led and which fired late."""

from __future__ import annotations

LAYERS = {"L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph", "L6_fusion"}


def test_layer_scores_requires_auth(client):
    assert client.get("/api/v1/entities/EMP-7f3a/layer-scores").status_code == 401


def test_layer_scores_shape(client, auth):
    r = client.get("/api/v1/entities/EMP-7f3a/layer-scores", headers=auth("analyst"))
    assert r.status_code == 200
    body = r.json()
    assert body["threshold_score"] == 70
    assert {s["layer"] for s in body["series"]} == LAYERS
    for s in body["series"]:
        assert s["label"]
        assert len(s["points"]) == 8
        for p in s["points"]:
            assert 0 <= p["score"] <= 100


def test_layer_scores_are_deterministic_scores(client, auth):
    # Same entity → same per-layer score sequence (deterministic wobble), regardless of wall clock.
    a = client.get("/api/v1/entities/EMP-7f3a/layer-scores", headers=auth("analyst")).json()
    b = client.get("/api/v1/entities/EMP-7f3a/layer-scores", headers=auth("analyst")).json()
    seq = lambda body: {s["layer"]: [p["score"] for p in s["points"]] for s in body["series"]}
    assert seq(a) == seq(b)
