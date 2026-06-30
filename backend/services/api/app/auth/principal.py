"""Authenticated principal (BACKEND-2/3).

Built from a validated JWT. Carries the role (for RBAC), the case scope (assigned alert ids —
Analyst need-to-know), and the ``de_identified_only`` flag (Model Engineer). No PII.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.auth.rbac import is_allowed
from app.schemas.common import Capability, Role


class Principal(BaseModel):
    user_id: str = Field(..., description="Tokenized user id, e.g. EMP-aud1 / svc-ingest")
    role: Role
    display_name: str = ""
    assigned_alerts: set[str] = Field(
        default_factory=set, description="Case scope — Analyst sees only these (Part 19.6)"
    )
    de_identified_only: bool = Field(
        False, description="Model Engineer: may only see de-identified data (Part 24.1)"
    )
    scopes: list[str] = Field(default_factory=list, description="Service-account token scopes")
    token_id: str = ""

    def can(self, capability: Capability) -> bool:
        return is_allowed(self.role, capability)

    @property
    def is_lead_or_above(self) -> bool:
        return self.role in (Role.TEAM_LEAD, Role.PLATFORM_ADMIN)

    @property
    def is_senior_plus(self) -> bool:
        return self.role in (
            Role.SENIOR_INVESTIGATOR,
            Role.TEAM_LEAD,
            Role.COMPLIANCE_OFFICER,
        )
