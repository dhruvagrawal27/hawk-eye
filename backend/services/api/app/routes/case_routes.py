"""Case routes (cross-job: serves FRONTEND's [FE-proposed] /cases surface).

A case wraps one entity's alert(s) with a status workflow, assignee, notes, and audit history.
Cases are derived from the alert store (grouped by entity); case-specific state lives in a small
in-memory overlay. Every view/mutation writes an audit event. Blueprint Part 11 / 16 / 24.4.
"""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.cases import (
    CASE_STATUSES,
    AssignBody,
    CaseDetail,
    CaseHistoryEvent,
    CaseNote,
    CasePage,
    CaseSummary,
    NoteBody,
    StatusBody,
)
from app.schemas.common import Capability, iso_z, new_audit_id, utcnow
from app.store.alert_store import ALERTS

router = APIRouter(tags=["cases"])

_SEV_RANK = {"low": 0, "medium": 1, "high": 2}
# case_id -> overlay {status, assignee, notes[], history[]}
_OVERLAY: dict[str, dict] = {}


def _case_id(entity_id: str) -> str:
    return f"case_{entity_id}"


def _overlay(case_id: str) -> dict:
    return _OVERLAY.setdefault(
        case_id, {"status": None, "assignee": None, "notes": [], "history": []}
    )


def _build_summaries() -> dict[str, dict]:
    """Group alerts by entity into case skeletons (highest severity + summed exposure)."""
    by_entity: dict[str, dict] = {}
    for a in ALERTS.all():
        c = by_entity.setdefault(
            a.entity_id,
            {
                "alerts": [],
                "severity": "low",
                "exposure": 0,
                "created": a.created_ts,
                "sla": a.sla_due_ts,
            },
        )
        c["alerts"].append(a)
        if _SEV_RANK.get(str(a.severity), 0) >= _SEV_RANK.get(c["severity"], 0):
            c["severity"] = str(a.severity)
        c["exposure"] += int(a.exposure_inr or 0)
        if a.created_ts and (not c["created"] or a.created_ts < c["created"]):
            c["created"] = a.created_ts
    return by_entity


def _summary(entity_id: str, c: dict) -> CaseSummary:
    cid = _case_id(entity_id)
    ov = _overlay(cid)
    alerts = sorted(c["alerts"], key=lambda a: a.created_ts or "")
    return CaseSummary(
        case_id=cid,
        title=f"Investigation — {entity_id}",
        entity_id=entity_id,
        status=ov["status"] or (alerts[0].status if alerts else "open"),
        severity=c["severity"],
        assignee=ov["assignee"] or (alerts[0].assignee if alerts else None),
        alert_ids=[a.alert_id for a in alerts],
        created_ts=c["created"],
        updated_ts=ov["history"][0]["ts"] if ov["history"] else c["created"],
        sla_due_ts=c["sla"],
        exposure_inr=c["exposure"],
    )


@router.get("/cases", response_model=CasePage)
def list_cases(
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> CasePage:
    by_entity = _build_summaries()
    items = [_summary(e, c) for e, c in by_entity.items()]
    items.sort(key=lambda s: _SEV_RANK.get(str(s.severity), 0), reverse=True)
    AUDIT.write(actor=principal.user_id, actor_role=principal.role, action="case.list")
    return CasePage(items=items, total=len(items))


def _detail_or_404(case_id: str) -> CaseDetail:
    by_entity = _build_summaries()
    for entity_id, c in by_entity.items():
        if _case_id(entity_id) == case_id:
            summary = _summary(entity_id, c)
            ov = _overlay(case_id)
            return CaseDetail(
                **summary.model_dump(),
                alerts=sorted(c["alerts"], key=lambda a: a.created_ts or ""),
                notes=[CaseNote(**n) for n in ov["notes"]],
                history=[CaseHistoryEvent(**h) for h in ov["history"]],
            )
    raise HTTPException(status_code=404, detail="case not found")


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: str, principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS))
) -> CaseDetail:
    detail = _detail_or_404(case_id)
    AUDIT.write(
        actor=principal.user_id, actor_role=principal.role, action="case.view", target=case_id
    )
    return detail


def _push_history(case_id: str, principal: Principal, action: str, detail: str | None) -> str:
    ts = iso_z(utcnow())
    _overlay(case_id)["history"].insert(
        0,
        {
            "id": new_audit_id(),
            "ts": ts,
            "actor": principal.user_id,
            "actor_role": (
                principal.role.value if hasattr(principal.role, "value") else str(principal.role)
            ),
            "action": action,
            "detail": detail,
        },
    )
    return ts


@router.post("/cases/{case_id}/status", response_model=CaseDetail)
def set_case_status(
    case_id: str,
    body: StatusBody,
    principal: Principal = Depends(require_capability(Capability.TRIAGE_ASSIGN)),
) -> CaseDetail:
    _detail_or_404(case_id)  # 404 if unknown
    if body.status not in CASE_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {CASE_STATUSES}")
    ov = _overlay(case_id)
    ov["status"] = body.status
    _push_history(case_id, principal, "status_changed", f"→ {body.status}")
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="case.status",
        target=case_id,
        detail={"status": body.status},
    )
    return _detail_or_404(case_id)


@router.post("/cases/{case_id}/assign", response_model=CaseDetail)
def assign_case(
    case_id: str,
    body: AssignBody,
    principal: Principal = Depends(require_capability(Capability.TRIAGE_ASSIGN)),
) -> CaseDetail:
    _detail_or_404(case_id)
    _overlay(case_id)["assignee"] = body.assignee
    _push_history(case_id, principal, "assigned", f"→ {body.assignee}")
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="case.assign",
        target=case_id,
        detail={"assignee": body.assignee},
    )
    return _detail_or_404(case_id)


@router.post("/cases/{case_id}/notes", response_model=CaseDetail)
def add_case_note(
    case_id: str,
    body: NoteBody = Body(...),
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> CaseDetail:
    _detail_or_404(case_id)
    ts = iso_z(utcnow())
    _overlay(case_id)["notes"].insert(
        0,
        {
            "id": new_audit_id(),
            "author": principal.user_id,
            "author_role": (
                principal.role.value if hasattr(principal.role, "value") else str(principal.role)
            ),
            "ts": ts,
            "body": body.body,
        },
    )
    _push_history(case_id, principal, "note_added", None)
    AUDIT.write(
        actor=principal.user_id, actor_role=principal.role, action="case.note", target=case_id
    )
    return _detail_or_404(case_id)
