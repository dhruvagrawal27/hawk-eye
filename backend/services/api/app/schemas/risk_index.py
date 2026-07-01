"""Per-user insider-risk index contract (M2.1).

The ML batch pipeline (`ml.pipelines.insider_risk_index`) computes this over the trailing window and
writes it to the entity store; the backend endpoint READS it (backend has no ML dependency). It is a
displayed, explained 0–100 score for a human — ALERT-ONLY, never an automated action; composition
weights are stubs pending labelled calibration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskIndexComponent(BaseModel):
    name: str
    group: str = Field(..., description="hr | access | anomaly")
    value: float = Field(..., ge=0.0, le=1.0)
    detail: str = ""


class RiskIndexResponse(BaseModel):
    employee_id: str
    composite: int = Field(..., ge=0, le=100, description="0–100 insider-risk index")
    hr_score: float = Field(..., ge=0.0, le=1.0)
    access_score: float = Field(..., ge=0.0, le=1.0)
    anomaly_score: float = Field(..., ge=0.0, le=1.0)
    components: list[RiskIndexComponent] = Field(default_factory=list)
    top_drivers: list[str] = Field(default_factory=list)
    updated_ts: str | None = None
    calibrated: bool = Field(
        False, description="False = stub weights (do not auto-action; human review only)"
    )
