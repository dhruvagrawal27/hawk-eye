"""FastAPI auth dependencies (BACKEND-2/3).

* ``get_principal``      — validate the bearer JWT → Principal (401 on missing/invalid).
* ``require_capability`` — RBAC gate per the 8×9 matrix (403 on DENY).
* ``require_role``       — explicit role gate where the API table names a role.
* ``require_capabilities`` — require all of several capabilities.

Every non-public route depends on at least ``get_principal`` so it 401s without a valid token.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status

from app.auth import rbac
from app.auth.oidc import TokenError, validate_access_token
from app.auth.principal import Principal
from app.schemas.common import Capability, Role


def get_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Validate ``Authorization: Bearer <jwt>`` and return the Principal."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        return validate_access_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _enforce(principal: Principal, capability: Capability) -> None:
    """Raise 403 unless the principal's role grants ``capability``.

    Service accounts use **scoped tokens** (Part 24.1 ``scoped_token`` / ``write_only``): even where
    the matrix marks a capability conditional, the capability must be present in the token's
    ``scopes`` — so a service account whose scope is ``audit:write`` cannot READ the audit trail.
    """
    grant = rbac.decision(principal.role, capability)
    if not grant.permitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"role {principal.role.value} lacks capability {capability.value}",
        )
    if principal.role == Role.SERVICE_ACCOUNT and capability.value not in principal.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"service-account token lacks scope for {capability.value} (scoped/write-only)",
        )


def require_capability(capability: Capability) -> Callable[[Principal], Principal]:
    """Dependency factory: 403 unless the principal's role grants ``capability``."""

    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        _enforce(principal, capability)
        return principal

    return _dep


def require_capabilities(*capabilities: Capability) -> Callable[[Principal], Principal]:
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        for cap in capabilities:
            _enforce(principal, cap)
        return principal

    return _dep


def require_role(*roles: Role) -> Callable[[Principal], Principal]:
    def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"requires one of roles {[r.value for r in roles]}",
            )
        return principal

    return _dep
