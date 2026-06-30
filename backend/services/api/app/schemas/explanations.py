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


class Explanation(BaseModel):
    alert_id: str
    entity_id: str
    risk_score: int = Field(..., ge=0, le=100)
    shap: list[ShapFeature] = Field(default_factory=list)
    rule_provenance: list[RuleProvenance] = Field(default_factory=list)
    sequence_attention: list[AttentionStep] = Field(default_factory=list)
    graph_evidence: list[str] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
