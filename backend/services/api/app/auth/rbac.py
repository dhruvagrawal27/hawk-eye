"""RBAC permission matrix — 8 roles × 9 capabilities (BACKEND-3, blueprint Part 24.1).

Encoded EXACTLY from the Part 24.1 table:
  ✅ allowed → ALLOW · ⚠️ conditional → CONDITIONAL (route enforces the note) · ❌ → DENY.

A CONDITIONAL grant means the capability is permitted *subject to a constraint the route must
additionally enforce* — case-scoping (Analyst sees assigned only), de-identification (Model
Engineer sees de-identified data only), mandatory logging (all unmask), or a second-person
sign-off (model promotion). PII unmask is a SEPARATE, audited capability (never implied by
"view alerts"). SoD constraints live in ``app.auth.sod``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.schemas.common import Capability, Role


class Permission(str, Enum):
    ALLOW = "allow"
    CONDITIONAL = "conditional"
    DENY = "deny"


@dataclass(frozen=True)
class Grant:
    permission: Permission
    note: str = ""

    @property
    def permitted(self) -> bool:
        return self.permission in (Permission.ALLOW, Permission.CONDITIONAL)


A = Grant(Permission.ALLOW)
X = Grant(Permission.DENY)


def C(note: str) -> Grant:  # noqa: N802 - terse matrix helper
    return Grant(Permission.CONDITIONAL, note)


# Column order matches Part 24.1 exactly.
_CAPS = (
    Capability.VIEW_ALERTS,
    Capability.TRIAGE_ASSIGN,
    Capability.DISPOSITION,
    Capability.REQUEST_BLOCK,
    Capability.UNMASK_PII,
    Capability.TUNE_RULES,
    Capability.TRAIN_DEPLOY_MODELS,
    Capability.VIEW_AUDIT,
    Capability.ADMIN,
)

# ruff: noqa: E241  (aligned matrix is intentional)
_ROWS: dict[Role, tuple[Grant, ...]] = {
    # role:                view             triage   disp           block            unmask                       tune                          train/deploy                  audit               admin
    Role.ANALYST:          (C("assigned_only"), A,   A,             C("request_only"), C("case_scoped_logged"),    X,                            X,                            X,                  X),
    Role.SENIOR_INVESTIGATOR: (A,            A,       A,             A,               C("logged"),                 X,                            X,                            C("view_own"),      X),
    Role.TEAM_LEAD:        (A,               A,       C("override"), C("approve"),    C("logged"),                 C("propose_only"),            X,                            A,                  X),
    Role.COMPLIANCE_OFFICER: (A,             X,       X,             X,               C("logged"),                 C("change_controlled"),       X,                            A,                  X),
    Role.AUDITOR:          (C("read_only"),  X,       X,             X,               X,                           X,                            X,                            A,                  X),
    Role.MODEL_ENGINEER:   (C("de_identified_only"), X, X,          X,               X,                           X,                            C("with_signoff"),            C("view_own"),      X),
    Role.PLATFORM_ADMIN:   (X,               X,       X,             X,               X,                           X,                            C("deploy_infra_only"),       A,                  A),
    Role.SERVICE_ACCOUNT:  (C("scoped_token"), X,     X,             X,               X,                           X,                            X,                            C("write_only"),    X),
}

MATRIX: dict[Role, dict[Capability, Grant]] = {
    role: dict(zip(_CAPS, grants)) for role, grants in _ROWS.items()
}


def decision(role: Role | str, capability: Capability | str) -> Grant:
    """Return the (allow/conditional/deny) grant for ``(role, capability)``."""
    role = Role(role)
    capability = Capability(capability)
    return MATRIX[role].get(capability, X)


def is_allowed(role: Role | str, capability: Capability | str) -> bool:
    """True if the role may exercise the capability (ALLOW or CONDITIONAL)."""
    return decision(role, capability).permitted


def capabilities_for(role: Role | str) -> dict[str, str]:
    """All permitted capabilities for a role → note (used to build the frontend capability set)."""
    role = Role(role)
    return {
        cap.value: grant.note or "allowed"
        for cap, grant in MATRIX[role].items()
        if grant.permitted
    }


def assert_matrix_complete() -> None:
    """Self-check invoked at import time: every (role × capability) cell is defined."""
    assert len(MATRIX) == 8, f"expected 8 roles, got {len(MATRIX)}"
    for role, row in MATRIX.items():
        missing = [c for c in Capability if c not in row]
        assert not missing, f"role {role} missing capabilities {missing}"
        assert len(row) == 9, f"role {role} has {len(row)} capabilities, expected 9"


assert_matrix_complete()
