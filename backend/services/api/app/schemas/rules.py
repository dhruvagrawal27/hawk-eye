"""Rule/threshold CRUD contracts with four-eyes approval (BACKEND-8, blueprint Part 24.2/31.3)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Severity


class RuleSummary(BaseModel):
    code: str = Field(..., examples=["NEW_BENEFICIARY_THEN_HIGHVALUE"])
    name: str
    version: str
    enabled: bool
    severity: Severity
    hard_hit: bool = Field(False, description="Hard-hit rules feed the L1 short-circuit")
    description: str = ""
    params: dict = Field(default_factory=dict)


class RuleChangeRequest(BaseModel):
    """A *proposed* change — does not take effect until a second approver signs off (four-eyes)."""

    code: str
    name: str | None = None
    enabled: bool | None = None
    severity: Severity | None = None
    hard_hit: bool | None = None
    description: str | None = None
    params: dict | None = None
    change_reason: str = Field(..., description="Why the change is needed (audited)")


class RuleChangeProposal(BaseModel):
    change_id: str
    code: str
    proposed_by: str
    status: str = Field("pending_approval", description="pending_approval | approved | rejected")
    diff: dict = Field(default_factory=dict)
    audit_id: str


class RuleApproval(BaseModel):
    change_id: str
    approve: bool = True
    approver_notes: str = ""


class RuleApprovalResult(BaseModel):
    change_id: str
    code: str
    status: str
    new_version: str | None = None
    audit_id: str
