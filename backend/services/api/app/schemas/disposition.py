"""EDD disposition + feedback + block-request contracts (BACKEND-20, blueprint Part 24.5c).

ALERT-ONLY: the disposition *is* the classification — a mandatory human decision (natural
justice, SBI v. Rajesh Agarwal 2023). No code path auto-classifies. ``block-request`` is
Analyst→Lead-approves, never automatic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import DispositionOutcome


class DispositionRequest(BaseModel):
    outcome: DispositionOutcome = Field(..., examples=["fraud"])
    notes: str = Field("", description="Investigator rationale (free text)")
    evidence_ids: list[str] = Field(
        default_factory=list, examples=[["evt_8f2a1c90", "evt_8f2a1d04"]]
    )


class DispositionResponse(BaseModel):
    """Exact Part 24.5c response shape."""

    alert_id: str = Field(..., examples=["alr_3d7e22"])
    status: str = Field(..., examples=["confirmed_fraud"])
    label_written: bool = True
    feedback_queued_for_retraining: bool = True
    audit_id: str = Field(..., examples=["aud_99f0c1"])


class AssignRequest(BaseModel):
    assignee: str = Field(..., description="Investigator id to assign/claim", examples=["EMP-aud1"])


class FeedbackRequest(BaseModel):
    """Active-learning label submission (POST /feedback)."""

    alert_id: str
    label: DispositionOutcome
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    notes: str = ""


class FeedbackResponse(BaseModel):
    accepted: bool = True
    label_written: bool = True
    feedback_queued_for_retraining: bool = True
    audit_id: str


class BlockRequest(BaseModel):
    reason: str = Field(..., description="Why a block is being requested (human action)")
    evidence_ids: list[str] = Field(default_factory=list)


class BlockRequestResponse(BaseModel):
    """A *request*, never an executed block. Requires Lead approval to action downstream."""

    alert_id: str
    status: str = Field(
        "block_requested", description="Pending Lead approval — never auto-executed"
    )
    requires_approval_by: str = "team_lead"
    auto_blocked: bool = Field(
        False, description="Always False — the system never auto-blocks money"
    )
    audit_id: str
