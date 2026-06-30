"""Alert routes (BACKEND-19, blueprint Part 24.2 / 11).

GET /alerts (ranked by fused risk×exposure×confidence, deduped per entity, RBAC case-scoped) and
GET /alerts/{id}. Every single-alert view writes a who-viewed-whom audit event ("watch the
watchers"). Model Engineers see de-identified payloads only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit.writer import AUDIT
from app.auth.case_scope import _DEIDENTIFIED_ROLES, can_view_alert, filter_visible
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.alerts import Alert, AlertPage
from app.schemas.common import Capability
from app.store.alert_store import ALERTS

router = APIRouter(tags=["alerts"])


def _deidentify(alert: Alert, principal: Principal) -> Alert:
    """De-identified roles (Data Science + exec/board) see de-identified alerts: no exposure value,
    no entity linkage detail (docs/BANK_ROLES.md view = C("de_identified_only"))."""
    if principal.role not in _DEIDENTIFIED_ROLES:
        return alert
    clone = alert.model_copy(deep=True)
    clone.entity_id = "EMP-deident"
    clone.exposure_inr = 0
    clone.reason_codes = [rc for rc in clone.reason_codes if rc.source != "graph"]
    return clone


@router.get("/alerts", response_model=AlertPage)
def list_alerts(
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
    status: str | None = Query(None),
    risk_gte: int | None = Query(None, ge=0, le=100),
    assignee: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AlertPage:
    items, _ = ALERTS.query(
        status=status, risk_gte=risk_gte, assignee=assignee, limit=10_000, offset=0
    )
    visible = filter_visible(
        principal, items, id_of=lambda a: a.alert_id, assignee_of=lambda a: a.assignee
    )
    total = len(visible)
    page = visible[offset : offset + limit]
    page = [_deidentify(a, principal) for a in page]
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="alert.list",
        detail={"returned": len(page), "filters": {"status": status, "risk_gte": risk_gte}},
    )
    next_offset = offset + limit if offset + limit < total else None
    return AlertPage(items=page, total=total, limit=limit, offset=offset, next_offset=next_offset)


@router.get("/alerts/{alert_id}", response_model=Alert)
def get_alert(
    alert_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> Alert:
    alert = ALERTS.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    if not can_view_alert(principal, alert_id, alert.assignee):
        raise HTTPException(status_code=403, detail="alert outside your case scope")
    # who-viewed-whom (Part 19.3 / 29.2)
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="alert.view",
        target=alert.entity_id,
        detail={"alert_id": alert_id},
    )
    return _deidentify(alert, principal)
