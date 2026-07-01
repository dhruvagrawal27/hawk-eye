"""M2.5 — RFA lifecycle routes (RBI Master Directions on Fraud Risk Management 2024).

Drives the staff-accountability examination lifecycle for an RFA-tagged entity:
open examination → record show-cause response → close (confirmed/exonerated), with the 180-day clock
and the natural-justice gate enforced by ``regulatory.rfa_lifecycle``. Compliance/Vigilance only;
every transition is audited. ALERT-ONLY: a person is confirmed only by a human after a hearing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.audit.writer import AUDIT
from app.auth.deps import require_role
from app.auth.principal import Principal
from app.schemas.common import Role, iso_z, utcnow
from regulatory.rfa_lifecycle import RFA_LIFECYCLE, RfaExamination, RfaTransitionError

router = APIRouter(tags=["rfa"])

_RFA_ROLES = require_role(Role.DGM_COMPLIANCE, Role.AGM_VIGILANCE)


class RfaExaminationOut(BaseModel):
    entity_id: str
    state: str
    triggered_ts: str
    examination_due_ts: str
    show_cause_due_ts: str
    alert_id: str | None = None
    show_cause_response_ts: str | None = None
    closed_ts: str | None = None
    outcome: str | None = None
    triggers: list[str] = Field(default_factory=list)
    window_expired: bool = False


class CloseBody(BaseModel):
    outcome: str = Field(..., pattern="^(confirmed|exonerated)$")


def _out(exam: RfaExamination) -> RfaExaminationOut:
    now = iso_z(utcnow())
    return RfaExaminationOut(**exam.to_dict(), window_expired=exam.window_expired(now))


def _audit(principal: Principal, entity_id: str, action: str, detail: dict | None = None) -> None:
    AUDIT.write(
        actor=principal.user_id, actor_role=principal.role,
        action=f"rfa.{action}", target=entity_id, detail=detail or {},
    )


@router.get("/rfa/{entity_id}", response_model=RfaExaminationOut)
def get_rfa(entity_id: str, principal: Principal = Depends(_RFA_ROLES)) -> RfaExaminationOut:
    exam = RFA_LIFECYCLE.get(entity_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="no RFA examination for this entity")
    return _out(exam)


@router.post("/rfa/{entity_id}/examination", response_model=RfaExaminationOut)
def open_examination(
    entity_id: str, principal: Principal = Depends(_RFA_ROLES)
) -> RfaExaminationOut:
    try:
        exam = RFA_LIFECYCLE.open_examination(entity_id)
    except RfaTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(principal, entity_id, "examination.open")
    return _out(exam)


@router.post("/rfa/{entity_id}/show-cause", response_model=RfaExaminationOut)
def show_cause(entity_id: str, principal: Principal = Depends(_RFA_ROLES)) -> RfaExaminationOut:
    """Record that the staffer responded to the show-cause notice (natural-justice gate)."""
    try:
        exam = RFA_LIFECYCLE.record_show_cause_response(entity_id, response_ts=iso_z(utcnow()))
    except RfaTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(principal, entity_id, "show_cause.response")
    return _out(exam)


@router.post("/rfa/{entity_id}/close", response_model=RfaExaminationOut)
def close_rfa(
    entity_id: str, body: CloseBody, principal: Principal = Depends(_RFA_ROLES)
) -> RfaExaminationOut:
    try:
        exam = RFA_LIFECYCLE.close(entity_id, outcome=body.outcome, now_ts=iso_z(utcnow()))
    except RfaTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _audit(principal, entity_id, "close", {"outcome": body.outcome})
    return _out(exam)
