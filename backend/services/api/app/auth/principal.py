"""Authenticated principal (BACKEND-2/3).

Built from a validated JWT. Carries the role (for RBAC), the case scope (assigned alert ids —
Relationship Manager need-to-know), and the ``de_identified_only`` flag (Data Science / exec &
board see de-identified aggregates only). No PII.
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
        default_factory=set,
        description="Case scope — Relationship Manager sees only these (BANK_ROLES.md)",
    )
    de_identified_only: bool = Field(
        False,
        description="Data Science / exec & board: may only see de-identified data (BANK_ROLES.md)",
    )
    scopes: list[str] = Field(default_factory=list, description="Service-account token scopes")
    token_id: str = ""

    def can(self, capability: Capability) -> bool:
        return is_allowed(self.role, capability)

    @property
    def is_lead_or_above(self) -> bool:
        return self.role in (Role.AGM_VIGILANCE, Role.IT_ADMIN)

    @property
    def is_senior_plus(self) -> bool:
        return self.role in (
            Role.BRANCH_MANAGER,
            Role.AGM_VIGILANCE,
            Role.DGM_COMPLIANCE,
        )
