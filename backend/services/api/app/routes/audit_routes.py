"""Audit route (BACKEND-22, blueprint Part 24.2 l.913 / 19.3 / 29.2).

GET /audit — immutable trail incl. who-viewed-whom (Auditor / VIEW_AUDIT). Investigators' actions
are audited and subject to fairness review ("watch the watchers"). Admin user/role management lives
in ``admin_routes``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.rbac import decision
from app.schemas.audit import AuditPage
from app.schemas.common import Capability

router = APIRouter(tags=["audit"])


@router.get("/audit", response_model=AuditPage)
def get_audit(
    principal: Principal = Depends(require_capability(Capability.VIEW_AUDIT)),
    actor: str | None = Query(None),
    entity: str | None = Query(None, description="who-viewed-whom: filter by subject entity"),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> AuditPage:
    # RBAC ⚠️ "view own" (Senior Investigator, Model Engineer): restrict to the caller's own actions
    # (Part 24.1). Auditor / Compliance / Team Lead / Platform Admin get the full trail.
    if decision(principal.role, Capability.VIEW_AUDIT).note == "view_own":
        actor = principal.user_id
    items, total = AUDIT.query(
        actor=actor, target=entity, action=action, limit=limit, offset=offset
    )
    # Reading the audit trail is itself an audited action (watch-the-watchers, recursively).
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="audit.view",
        detail={"filters": {"actor": actor, "entity": entity, "action": action}},
    )
    return AuditPage(items=items, total=total, limit=limit, offset=offset)
