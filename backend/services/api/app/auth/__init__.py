"""Auth: OIDC/JWT (BACKEND-2) + RBAC 8×9 matrix, SoD, case-scope (BACKEND-3)."""

from app.auth import case_scope, oidc, rbac, sod
from app.auth.deps import (
    get_principal,
    require_capabilities,
    require_capability,
    require_role,
)
from app.auth.principal import Principal

__all__ = [
    "case_scope",
    "oidc",
    "rbac",
    "sod",
    "get_principal",
    "require_capabilities",
    "require_capability",
    "require_role",
    "Principal",
]
