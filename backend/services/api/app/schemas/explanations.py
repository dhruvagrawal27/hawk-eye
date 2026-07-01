"""Explanation contract: SHAP + rule provenance + sequence attention (BACKEND-19, Part 11/24.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.alerts import ReasonCode


class ShapFeature(BaseModel):
    feature: str
    contribution: float
    value: float | str | None = None


class RuleProvenance(BaseModel):
    code: str
    version: str
    detail: str = ""
    severity_hint: str | None = None


class AttentionStep(BaseModel):
    """One step of L4 sequence attention (LAXCAT-style)."""

    step: int
    verb: str
    ts: str | None = None
    weight: float


class FusionComponent(BaseModel):
    """One detection layer's contribution to the L6 fusion (transparent decomposition)."""

    layer: str  # LAYER_COLUMNS key: L1_rule | L2_unsupervised | L3_gbdt | L4_sequence | L5_graph
    label: str
    sublabel: str
    proba: float | None = None  # raw 0–1 layer score; None ⇒ the layer did not run
    weight: float  # meta-learner coefficient this layer was weighed by
    contribution: float = 0.0  # weight × proba (0 when the layer did not run)


class FusionBreakdown(BaseModel):
    """The headline 'why this fired': fused probability vs the decision threshold, decomposed into
    every layer's raw score, weight, and weighted pull, plus cross-layer agreement and an honest
    decisive-layer / rescued-by counterfactual. Sourced from ``fusion.build_breakdown``."""

    fused: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(..., ge=0.0, le=1.0)
    calibrated_score: int = Field(..., ge=0, le=100)
    agreement: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    hard_hit: bool = False
    rescued: bool = False
    decisive_layer: str | None = None
    components: list[FusionComponent] = Field(default_factory=list)
    meta_version: str = ""


class Explanation(BaseModel):
    alert_id: str
    entity_id: str
    risk_score: int = Field(..., ge=0, le=100)
    shap: list[ShapFeature] = Field(default_factory=list)
    rule_provenance: list[RuleProvenance] = Field(default_factory=list)
    sequence_attention: list[AttentionStep] = Field(default_factory=list)
    graph_evidence: list[str] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    fusion: FusionBreakdown | None = None
