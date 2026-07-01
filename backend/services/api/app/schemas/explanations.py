"""Explanation contract: SHAP + rule provenance + sequence attention (BACKEND-19, Part 11/24.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.alerts import ReasonCode


class ShapFeature(BaseModel):
    feature: str
    contribution: float
    value: float | str | None = None
    percentile: float | None = None  # 0–1 peer percentile of this feature's value


class RuleProvenance(BaseModel):
    code: str
    version: str
    detail: str = ""
    severity_hint: str | None = None


class AttentionVariable(BaseModel):
    """One variable's attention weight at a step — the *variable* axis of LAXCAT variable×temporal."""

    name: str
    weight: float


class AttentionStep(BaseModel):
    """One step of L4 sequence attention (LAXCAT-style)."""

    step: int
    verb: str
    ts: str | None = None
    weight: float  # temporal attention (time axis)
    variables: list[AttentionVariable] = Field(default_factory=list)  # variable axis


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


class ModelLineageEntry(BaseModel):
    """Which model produced a layer's score, and its governance posture (MRMF / FREE-AI)."""

    layer: str  # L1_rule | L2_unsupervised | L3_gbdt | L4_sequence | L5_graph | L6_fusion
    model_id: str
    version: str
    stage: str = "Production"  # Production | Staging | Challenger | Archived
    risk_tier: str | None = None  # tier-1-critical … tier-4-low
    signed: bool = False  # signature verifies (cosign/sigstore in prod)
    approving_reviewer: str | None = None  # SoD sign-off
    metrics: dict = Field(default_factory=dict)


class GraphEvidenceNode(BaseModel):
    """One node in the L5 collusion subgraph (for the inline mini-graph render)."""

    id: str
    label: str
    type: str  # employee | beneficiary | account | device | ip
    importance: float = 0.0  # 0–1, drives node size / prominence


class GraphEvidenceEdge(BaseModel):
    source: str
    target: str
    type: str  # maker_checker | pays | shares_device | ...
    importance: float = 0.0  # 0–1, GNNExplainer edge attribution


class GraphEvidence(BaseModel):
    """Structured L5 graph evidence — the ring / GNNExplainer subgraph, renderable as a mini-graph."""

    ring_id: str | None = None
    summary: str = ""
    explainer_model: str | None = None
    nodes: list[GraphEvidenceNode] = Field(default_factory=list)
    edges: list[GraphEvidenceEdge] = Field(default_factory=list)


class Explanation(BaseModel):
    alert_id: str
    entity_id: str
    risk_score: int = Field(..., ge=0, le=100)
    shap: list[ShapFeature] = Field(default_factory=list)
    rule_provenance: list[RuleProvenance] = Field(default_factory=list)
    sequence_attention: list[AttentionStep] = Field(default_factory=list)
    graph_evidence: list[str] = Field(default_factory=list)
    graph: GraphEvidence | None = None
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    fusion: FusionBreakdown | None = None
    model_lineage: list[ModelLineageEntry] = Field(default_factory=list)
