"""Phase 2 — Rich explainability. The explanation endpoint must carry the LAXCAT variable×temporal
attention (per-step variable weights) and SHAP peer percentiles — the depth the old contract dropped
(one temporal bar, no baseline context)."""

from __future__ import annotations


def test_attention_steps_carry_per_variable_weights(client, auth):
    r = client.get("/api/v1/explanations/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    steps = r.json()["sequence_attention"]
    assert steps, "expected synthesized L4 attention steps"
    for st in steps:
        names = {v["name"] for v in st["variables"]}
        # the four LAXCAT variables that form the heatmap rows
        assert {"verb", "log_amount", "off_hours", "velocity_1h"} <= names
        for v in st["variables"]:
            assert 0.0 <= v["weight"] <= 1.0


def test_shap_features_carry_peer_percentile(client, auth):
    r = client.get("/api/v1/explanations/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    for feat in r.json()["shap"]:
        assert feat["percentile"] is not None
        assert 0.0 <= feat["percentile"] <= 1.0


def test_explanation_carries_structured_graph_subgraph(client, auth):
    # Deferred polish: the L5 evidence is now a structured subgraph (drawable), not just text.
    r = client.get("/api/v1/explanations/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    graph = r.json()["graph"]
    assert graph is not None
    assert len(graph["nodes"]) >= 2
    assert graph["explainer_model"] == "GNNExplainer"
    ids = {n["id"] for n in graph["nodes"]}
    for e in graph["edges"]:
        assert e["source"] in ids and e["target"] in ids
        assert 0.0 <= e["importance"] <= 1.0
