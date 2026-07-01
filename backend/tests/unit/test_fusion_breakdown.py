"""Phase 1 — Detection Transparency: the L6 fusion breakdown (per-layer decomposition).

Verifies the transparent per-layer decomposition that powers the L7 "why this fired" panel:
every layer's raw 0–1 score, the meta coefficient, its weighted pull, cross-layer agreement, and
the decisive-layer / rescued-by counterfactual — carried through the pipeline and served on
GET /explanations/{id}. This is the data the old contract discarded (only enum names survived).
"""

from __future__ import annotations

from fusion.service import (
    DECISION_THRESHOLD_PROB,
    LAYER_META_WEIGHTS,
    DEFAULT_FUSION,
    build_breakdown,
)

CANONICAL_ORDER = ["L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph"]


def test_build_breakdown_has_five_ordered_components_with_correct_math():
    scores = {
        "L1_rule": 0.4,
        "L2_unsupervised": 0.55,
        "L3_gbdt": 0.62,
        "L4_sequence": 0.41,
        "L5_graph": 1.0,
    }
    b = build_breakdown(scores, 0.9, hard_hit=False, confidence=0.86)

    assert [c["layer"] for c in b["components"]] == CANONICAL_ORDER
    for c in b["components"]:
        assert c["label"] and c["sublabel"]
        assert c["weight"] == LAYER_META_WEIGHTS[c["layer"]]
        # contribution == weight × proba for every fired layer
        assert abs(c["contribution"] - c["weight"] * c["proba"]) < 1e-6
    assert 0.0 <= b["agreement"] <= 1.0
    assert b["threshold"] == round(DECISION_THRESHOLD_PROB, 4)
    assert b["calibrated_score"] == 90  # round(0.9 * 100)
    assert b["meta_version"]


def test_absent_layer_reports_did_not_run():
    # Degraded / cold-start: only the rule floor ran — the other four are honestly None.
    b = build_breakdown({"L1_rule": 0.5}, 0.5, hard_hit=False, confidence=0.5)
    by = {c["layer"]: c for c in b["components"]}
    assert by["L1_rule"]["proba"] == 0.5
    for layer in ("L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph"):
        assert by[layer]["proba"] is None
        assert by[layer]["contribution"] == 0.0


def test_rescued_when_gbdt_alone_would_miss_but_graph_carries_it():
    # GBDT below the bar, fused above it, graph present ⇒ rescued, decisive = the graph layer.
    scores = {"L3_gbdt": 0.30, "L5_graph": 1.0}
    b = build_breakdown(scores, 0.85, hard_hit=False, confidence=0.7)
    assert b["rescued"] is True
    assert b["decisive_layer"] == "L5_graph"


def test_not_rescued_when_gbdt_clears_the_bar():
    b = build_breakdown({"L3_gbdt": 0.9}, 0.9, hard_hit=False, confidence=0.8)
    assert b["rescued"] is False
    assert b["decisive_layer"] == "L3_gbdt"


def test_fuse_populates_breakdown_and_layer_scores():
    out = DEFAULT_FUSION.fuse(
        scores={"L2_unsupervised": 0.55, "L3_gbdt": 0.62, "L4_sequence": 0.41},
        features={"maker_checker_pair_isolated": True},
        l1_score=0.4,
        l1_reason_codes=[{"source": "rule", "code": "OFF_HOURS_ACTIVITY", "detail": "x"}],
        graph_evidence=["isolated pair (ring RNG-12)"],
    )
    assert out.layer_scores["L5_graph"] == 1.0  # SoD/graph proxy fed the meta-learner
    assert set(out.layer_scores) == set(CANONICAL_ORDER)
    assert len(out.breakdown["components"]) == 5
    assert 0.0 <= out.agreement <= 1.0


def test_explanation_endpoint_returns_fusion(client, auth):
    # alr_demo01 (worked burst) is assigned to the RM ("analyst"): assigned-scope view is allowed.
    r = client.get("/api/v1/explanations/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    body = r.json()
    assert "fusion" in body and body["fusion"] is not None
    fusion = body["fusion"]
    assert len(fusion["components"]) == 5
    assert [c["layer"] for c in fusion["components"]] == CANONICAL_ORDER
    assert 0.0 <= fusion["agreement"] <= 1.0
    assert fusion["calibrated_score"] == round(fusion["fused"] * 100)
    # every fired component's contribution is its weight × proba (auditable arithmetic)
    for c in fusion["components"]:
        if c["proba"] is not None:
            assert abs(c["contribution"] - c["weight"] * c["proba"]) < 1e-6
