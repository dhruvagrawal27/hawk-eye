"""Case-management contracts (cross-job: serves FRONTEND's [FE-proposed] /cases routes).

A "case" is the investigation wrapper around one entity's alert(s): status workflow, assignee,
notes, and an audit history. Matches frontend/src/lib/types.ts CaseSummary/CaseDetail so the
connected dashboard renders without change. Blueprint Part 11 / 24.4 (case management screen).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.alerts import Alert
from app.schemas.common import Role, Severity

CASE_STATUSES = ("open", "in_progress", "escalated", "closed")


class CaseNote(BaseModel):
    id: str
    author: str
    author_role: Role | str | None = None
    ts: str
    body: str


class CaseHistoryEvent(BaseModel):
    id: str
    ts: str
    actor: str
    actor_role: Role | str | None = None
    action: str
    detail: str | None = None


class CaseSummary(BaseModel):
    case_id: str
    title: str
    entity_id: str
    status: str = "open"
    severity: Severity
    assignee: str | None = None
    alert_ids: list[str] = Field(default_factory=list)
    created_ts: str
    updated_ts: str
    sla_due_ts: str | None = None
    exposure_inr: int | None = 0


class CaseDetail(CaseSummary):
    alerts: list[Alert] = Field(default_factory=list)
    notes: list[CaseNote] = Field(default_factory=list)
    history: list[CaseHistoryEvent] = Field(default_factory=list)


class CasePage(BaseModel):
    items: list[CaseSummary]
    total: int


class StatusBody(BaseModel):
    status: str
    note: str | None = None


class AssignBody(BaseModel):
    assignee: str


class NoteBody(BaseModel):
    body: str
