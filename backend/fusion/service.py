"""L6 risk-fusion service (BACKEND-12, blueprint Part 18.1 l.572/585).

Produces a calibrated 0–100 risk score + severity × confidence + assembled reason codes (rule
provenance + SHAP top features + graph evidence) exactly matching the alert schema. The stacked
meta-learner is a stub (# STUB: ML L6 meta-model + calibrator); swapping in ML's fitted meta-model
changes only ``_meta_prob``. Decoupled from rules_engine/serving — the caller passes primitives.

Beyond the headline score it also emits a **transparent per-layer breakdown** (``build_breakdown``):
every layer's raw 0–1 score, the meta-learner coefficient it was weighed by, its weighted pull on
the fused probability, the SoD component, the fused probability vs the decision threshold,
cross-layer **agreement**, and an honest **decisive-layer / rescued-by** counterfactual. This is the
data the L7 explanation panel needs to answer "which layer pushed it over, and would any single
layer have caught it?" — not just the enum names in ``contributing_layers``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fusion.calibration import (
    HIGH_THRESHOLD,
    agreement_from,
    calibrate_probability,
    confidence_from,
    severity_for,
)
from fusion.reason_codes import assemble

L6_META_VERSION = "l6_meta@stub-2026.06.30"

# Decision threshold on the same 0–1 scale as the fused probability (an alert emits at the calibrated
# HIGH band). Kept here so the breakdown's "cleared the bar" / "rescued" logic matches what emits.
DECISION_THRESHOLD_PROB = HIGH_THRESHOLD / 100.0

# The stub meta-learner's per-layer coefficients (mirror of ``_meta_prob``). L5 graph enters the
# logistic as the SoD/collusion component. When ML's fitted meta-model lands, replace this map with
# its learned coefficients and the breakdown stays exact.
LAYER_META_WEIGHTS: dict[str, float] = {
    "L1_rule": 1.7,
    "L2_unsupervised": 1.2,
    "L3_gbdt": 2.4,
    "L4_sequence": 1.0,
    "L5_graph": 1.2,
}

# Presentation chrome carried alongside each component so the UI has a stable label without hardcoding.
LAYER_LABELS: dict[str, tuple[str, str]] = {
    "L1_rule": ("Rules / BRE", "L1 · deterministic"),
    "L2_unsupervised": ("Anomaly", "L2 · unsupervised"),
    "L3_gbdt": ("Gradient-boosted trees", "L3 · supervised tabular"),
    "L4_sequence": ("Sequence", "L4 · attention"),
    "L5_graph": ("Graph / collusion", "L5 · GNN"),
}


@dataclass
class FusionOutput:
    risk_score: int
    severity: str
    confidence: float
    prob: float
    contributing_layers: list[str] = field(default_factory=list)
    reason_codes: list[dict] = field(default_factory=list)
    model_versions: dict[str, str] = field(default_factory=dict)
    # Transparent decomposition (see build_breakdown). ``layer_scores`` holds only layers that ran.
    layer_scores: dict[str, float] = field(default_factory=dict)
    sod: float = 0.0
    agreement: float = 0.5
    breakdown: dict = field(default_factory=dict)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def build_breakdown(
    layer_scores: dict[str, float],
    fused_prob: float,
    *,
    hard_hit: bool,
    confidence: float,
) -> dict:
    """Assemble the transparent per-layer fusion breakdown (the L7 "why this fired" payload).

    ``layer_scores`` maps a LAYER_COLUMNS key (``L1_rule``/``L2_unsupervised``/``L3_gbdt``/
    ``L4_sequence``/``L5_graph``) to its raw 0–1 score; layers absent from the map are reported as
    ``proba=None`` ("did not run"). Contribution = coefficient × score. The decisive layer is the
    fired layer with the strongest weighted pull; ``rescued`` is true when the supervised GBDT alone
    would have fallen below the threshold but the fused score cleared it (the cross-layer signal a
    single tabular model cannot see).
    """
    threshold = round(DECISION_THRESHOLD_PROB, 4)
    fused = round(max(0.0, min(1.0, fused_prob)), 4)

    components: list[dict] = []
    for layer, weight in LAYER_META_WEIGHTS.items():
        proba = layer_scores.get(layer)
        label, sublabel = LAYER_LABELS[layer]
        fired = proba is not None
        contribution = round(weight * float(proba), 4) if fired else 0.0
        components.append(
            {
                "layer": layer,
                "label": label,
                "sublabel": sublabel,
                "proba": round(float(proba), 4) if fired else None,
                "weight": weight,
                "contribution": contribution,
            }
        )

    fired = [c for c in components if c["proba"] is not None]
    gbdt = next((c for c in components if c["layer"] == "L3_gbdt"), None)
    non_gbdt_fired = [c for c in fired if c["layer"] != "L3_gbdt"]
    rescued = bool(
        gbdt
        and gbdt["proba"] is not None
        and gbdt["proba"] < threshold
        and fused >= threshold
        and non_gbdt_fired
    )
    pool = non_gbdt_fired if rescued and non_gbdt_fired else fired
    decisive = max(pool, key=lambda c: c["contribution"], default=None)

    return {
        "fused": fused,
        "threshold": threshold,
        "calibrated_score": calibrate_probability(fused_prob),
        "agreement": agreement_from(list(layer_scores.values())),
        "confidence": round(confidence, 4),
        "hard_hit": bool(hard_hit),
        "rescued": rescued,
        "decisive_layer": decisive["layer"] if decisive else None,
        "components": components,
        "meta_version": L6_META_VERSION,
    }


class FusionService:
    """Online L6 fusion (Part 18)."""

    def fuse(
        self,
        *,
        scores: dict,
        model_versions: dict | None = None,
        features: dict | None = None,
        l1_score: float = 0.0,
        l1_hard_hit: bool = False,
        l1_reason_codes: list[dict] | None = None,
        graph_evidence: list[str] | None = None,
        sequence_attention: list[dict] | None = None,
    ) -> FusionOutput:
        features = features or {}
        scores = scores or {}
        l2 = float(scores.get("L2_unsupervised", 0.0) or 0.0)
        l3 = float(scores.get("L3_gbdt", 0.0) or 0.0)
        l4 = scores.get("L4_sequence")
        l4f = float(l4) if l4 is not None else None
        sod = (
            1.0
            if (
                features.get("maker_checker_same_actor")
                or features.get("maker_checker_pair_isolated")
            )
            else 0.0
        )

        prob = self._meta_prob(l1_score, l2, l3, l4f, sod)
        if l1_hard_hit:
            prob = max(prob, 0.85)  # a hard rule hit is HIGH by construction (Part 18.1)

        score100 = calibrate_probability(prob)
        severity = severity_for(score100, l1_hard_hit)
        layer_score_list = [s for s in (l2, l3, l4f) if s is not None] + [l1_score]
        confidence = confidence_from(layer_score_list, prob)

        contributing: list[str] = []
        if l1_reason_codes:
            contributing.append("L1_rules")
        if "L2_unsupervised" in scores:
            contributing.append("L2_unsupervised")
        if "L3_gbdt" in scores:
            contributing.append("L3_gbdt")
        if l4f is not None:
            contributing.append("L4_sequence")
        if graph_evidence:
            contributing.append("L5_graph")

        reason_codes = assemble(
            rule_reason_codes=l1_reason_codes or [],
            feature_vector=features,
            graph_evidence=graph_evidence,
            sequence_attention=sequence_attention,
        )

        # The per-layer raw scores that actually fed the meta-learner (only layers that ran).
        layer_scores: dict[str, float] = {"L1_rule": round(float(l1_score), 4)}
        if "L2_unsupervised" in scores:
            layer_scores["L2_unsupervised"] = round(l2, 4)
        if "L3_gbdt" in scores:
            layer_scores["L3_gbdt"] = round(l3, 4)
        if l4f is not None:
            layer_scores["L4_sequence"] = round(l4f, 4)
        if graph_evidence:
            layer_scores["L5_graph"] = round(sod, 4)

        breakdown = build_breakdown(
            layer_scores, prob, hard_hit=l1_hard_hit, confidence=confidence
        )

        versions = dict(model_versions or {})
        versions["L6_fusion"] = L6_META_VERSION
        return FusionOutput(
            risk_score=score100,
            severity=severity,
            confidence=confidence,
            prob=round(prob, 4),
            contributing_layers=contributing,
            reason_codes=reason_codes,
            model_versions=versions,
            layer_scores=layer_scores,
            sod=sod,
            agreement=breakdown["agreement"],
            breakdown=breakdown,
        )

    @staticmethod
    def _meta_prob(l1: float, l2: float, l3: float, l4: float | None, sod: float) -> float:
        z = -2.2 + 1.7 * l1 + 1.2 * l2 + 2.4 * l3 + 1.2 * sod
        if l4 is not None:
            z += 1.0 * l4
        return _sigmoid(z)


DEFAULT_FUSION = FusionService()
