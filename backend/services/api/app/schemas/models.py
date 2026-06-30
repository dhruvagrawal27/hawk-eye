"""Model registry / drift / metrics contracts (BACKEND-21, blueprint Part 24.2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    model_id: str = Field(..., examples=["l3_gbdt"])
    layer: str = Field(..., examples=["L3_gbdt"])
    version: str = Field(..., examples=["2026.06.30-1"])
    stage: str = Field(..., description="Production | Staging | Challenger | Archived")
    signed: bool = Field(..., description="Signature verified against registry (BACKEND-16)")
    training_data_hash: str | None = None
    feature_set_version: str | None = None
    approving_reviewer: str | None = None
    metrics: dict = Field(default_factory=dict)


class PromoteRequest(BaseModel):
    """Promotion requires a sign-off by a second person (SoD; promoter ≠ approver)."""

    to_stage: str = Field("Production", examples=["Production", "Staging"])
    signoff_by: str = Field(..., description="Second-person approver (≠ requester) — SoD")
    canary_percent: int = Field(10, ge=0, le=100)
    notes: str = ""


class PromoteResult(BaseModel):
    model_id: str
    version: str
    stage: str
    canary_percent: int
    signature_verified: bool
    audit_id: str


class DriftReport(BaseModel):
    model_id: str
    version: str
    data_drift_psi: float
    concept_drift: float
    drift_crossed: bool
    window: str = "rolling_30d"


class ModelQuality(BaseModel):
    model_id: str
    version: str
    pr_auc: float | None = None
    precision_at_k: float | None = None
    alert_to_true_fraud_ratio: float | None = None
    calibration_error: float | None = None
