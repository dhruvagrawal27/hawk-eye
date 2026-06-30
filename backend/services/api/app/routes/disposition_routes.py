"""EDD disposition + assign + block-request (BACKEND-20, blueprint Part 24.5c / 16 / 19.6 / 29.2).

ALERT-ONLY / human-in-the-loop: the disposition IS the classification (a mandatory human decision).
``block-request`` is a *request* — Analyst raises, Lead approves — and is **never** auto-executed.
The disposition writes a label (DATA label-source-4 / ML feedback loop) + an audit event and
returns the exact Part 24.5c response.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.auth.sod import SoDError, check_disposition
from app.observability.metrics import DISPOSITIONS
from app.schemas.common import AlertStatus, Capability, DispositionOutcome
from app.schemas.disposition import (
    AssignRequest,
    BlockRequest,
    BlockRequestResponse,
    DispositionRequest,
    DispositionResponse,
)
from app.store.alert_store import ALERTS

router = APIRouter(tags=["disposition"])

_OUTCOME_STATUS = {
    DispositionOutcome.FRAUD: AlertStatus.CONFIRMED_FRAUD,
    DispositionOutcome.FALSE_POSITIVE: AlertStatus.FALSE_POSITIVE,
    DispositionOutcome.INCONCLUSIVE: AlertStatus.INCONCLUSIVE,
}


def _alert_or_404(alert_id: str):
    alert = ALERTS.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    return alert


@router.post("/alerts/{alert_id}/assign")
def assign(
    alert_id: str,
    body: AssignRequest,
    principal: Principal = Depends(require_capability(Capability.TRIAGE_ASSIGN)),
) -> dict:
    _alert_or_404(alert_id)
    ALERTS.assign(alert_id, body.assignee)
    audit = AUDIT.write(actor=principal.user_id, actor_role=principal.role, action="alert.assign",
                        target=alert_id, detail={"assignee": body.assignee})
    return {"alert_id": alert_id, "assignee": body.assignee, "status": "assigned", "audit_id": audit.audit_id}


@router.post("/alerts/{alert_id}/disposition", response_model=DispositionResponse)
def disposition(
    alert_id: str,
    body: DispositionRequest,
    principal: Principal = Depends(require_capability(Capability.DISPOSITION)),
) -> DispositionResponse:
    alert = _alert_or_404(alert_id)
    # SoD: deployers cannot label/close; no self-review (Part 19.6).
    try:
        check_disposition(principal, alert.assignee, alert.entity_id)
    except SoDError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    new_status = _OUTCOME_STATUS[body.outcome]
    ALERTS.set_status(alert_id, new_status)
    audit = AUDIT.write(
        actor=principal.user_id, actor_role=principal.role, action="alert.disposition",
        target=alert.entity_id,
        detail={"alert_id": alert_id, "outcome": body.outcome.value, "evidence_ids": body.evidence_ids},
    )
    # Write the label + queue for retraining (DATA label-source-4 / ML feedback loop).
    label_record = {
        "alert_id": alert_id, "entity_id": alert.entity_id, "label": body.outcome.value,
        "notes": body.notes, "evidence_ids": body.evidence_ids, "labeled_by": principal.user_id,
        "audit_id": audit.audit_id, "source": "edd_disposition",
    }
    ALERTS.record_disposition(alert_id, label_record)
    ALERTS.queue_feedback(label_record)
    DISPOSITIONS.inc(outcome=body.outcome.value)
    return DispositionResponse(
        alert_id=alert_id,
        status=new_status.value,
        label_written=True,
        feedback_queued_for_retraining=True,
        audit_id=audit.audit_id,
    )


@router.post("/alerts/{alert_id}/block-request", response_model=BlockRequestResponse)
def block_request(
    alert_id: str,
    body: BlockRequest,
    principal: Principal = Depends(require_capability(Capability.REQUEST_BLOCK)),
) -> BlockRequestResponse:
    """Raise a block REQUEST (human action). Never auto-executed — Lead must approve downstream."""
    alert = _alert_or_404(alert_id)
    ALERTS.set_status(alert_id, AlertStatus.BLOCK_REQUESTED)
    audit = AUDIT.write(
        actor=principal.user_id, actor_role=principal.role, action="alert.block_request",
        target=alert.entity_id, detail={"alert_id": alert_id, "reason": body.reason, "auto_blocked": False},
    )
    ALERTS.record_block_request(alert_id, {"requested_by": principal.user_id, "reason": body.reason})
    return BlockRequestResponse(
        alert_id=alert_id, status="block_requested", requires_approval_by="team_lead",
        auto_blocked=False, audit_id=audit.audit_id,
    )
