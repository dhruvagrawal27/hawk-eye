"""L6 risk-fusion service (BACKEND-12, blueprint Part 18.1 l.572/585).

Produces a calibrated 0–100 risk score + severity × confidence + assembled reason codes (rule
provenance + SHAP top features + graph evidence) exactly matching the alert schema. The stacked
meta-learner is a stub (# STUB: ML L6 meta-model + calibrator); swapping in ML's fitted meta-model
changes only ``_meta_prob``. Decoupled from rules_engine/serving — the caller passes primitives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fusion.calibration import calibrate_probability, confidence_from, severity_for
from fusion.reason_codes import assemble

L6_META_VERSION = "l6_meta@stub-2026.06.30"


@dataclass
class FusionOutput:
    risk_score: int
    severity: str
    confidence: float
    prob: float
    contributing_layers: list[str] = field(default_factory=list)
    reason_codes: list[dict] = field(default_factory=list)
    model_versions: dict[str, str] = field(default_factory=dict)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


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
        layer_scores = [s for s in (l2, l3, l4f) if s is not None] + [l1_score]
        confidence = confidence_from(layer_scores, prob)

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
        )

    @staticmethod
    def _meta_prob(l1: float, l2: float, l3: float, l4: float | None, sod: float) -> float:
        z = -2.2 + 1.7 * l1 + 1.2 * l2 + 2.4 * l3 + 1.2 * sod
        if l4 is not None:
            z += 1.0 * l4
        return _sigmoid(z)


DEFAULT_FUSION = FusionService()
