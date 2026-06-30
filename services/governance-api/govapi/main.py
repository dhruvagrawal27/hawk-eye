"""Governance API — FastAPI (PLATFORM-32/35, blueprint Part 27.2 + Part 34).

Serves the governance DB records to the dashboard governance view (FRONTEND renders),
plus the AI/Model-Risk + ethics committee panels, approval queue, board-pack rollup,
the AI incident-reporting form (FREE-AI), and the go-live readiness gate.

Every read is audited (quis custodiet, Part 19.3 — even governance access is logged).
Runs on SQLite (local/CI) or Postgres (compose, GOVERNANCE_DB_URL). Auto-seeds on first
start if empty (AUTO_SEED=true) so the dashboard has data out of the box.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

import models  # /svc/models.py (container) or governance/db/models.py (conftest path)
import checklist  # go-live resolver

app = FastAPI(title="hawk-eye governance-api", version="1.0.0")
READS = Counter("governance_reads_total", "governance record reads", ["resource"])

ARTIFACTS = {
    "policies": models.Policy, "committees": models.Committee, "vendors": models.Vendor,
    "validations": models.ModelValidation, "dpia": models.DPIA,
    "security-reports": models.SecurityReport, "approvals": models.Approval,
    "incidents": models.Incident, "operating-metrics": models.OperatingMetric,
    "staffing": models.StaffingPlan, "uat": models.UATSignoff,
}


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


def _audit(session, actor: str, action: str, target: str) -> None:
    session.add(models.GovernanceAudit(actor=actor, action=action, target=target))
    session.commit()


@app.on_event("startup")
def _startup():
    models.init_db()
    if os.environ.get("AUTO_SEED", "true").lower() == "true":
        s = models.get_session()
        if s.query(models.GoLiveTick).count() == 0:
            try:
                import seed
                seed.main()
            except Exception:
                pass


@app.get("/health")
def health():
    return {"status": "ok", "service": "governance-api"}


@app.get("/api/v1/governance/committees/{committee_id}/minutes")
def committee_minutes(committee_id: int):
    s = models.get_session()
    rows = [_row(o) for o in s.query(models.CommitteeMinutes).filter_by(committee_id=committee_id).all()]
    return {"committee_id": committee_id, "minutes": rows}


@app.get("/api/v1/governance/approval-queue")
def approval_queue():
    """PLATFORM-35: pending approvals awaiting a committee decision."""
    s = models.get_session()
    rows = [_row(o) for o in s.query(models.Approval).filter_by(decision="pending").all()]
    return {"pending": rows, "count": len(rows)}


@app.get("/api/v1/governance/board-pack")
def board_pack():
    """PLATFORM-35: board/SCBMF-pack rollup across the inventory."""
    s = models.get_session()
    return {
        "models_validated": s.query(models.ModelValidation).filter_by(signoff_status="signed_off").count(),
        "approvals": s.query(models.Approval).filter_by(decision="approved").count(),
        "open_incidents": s.query(models.Incident).filter_by(status="open").count(),
        "vapt_passed": s.query(models.SecurityReport).filter_by(report_type="vapt", status="passed").count() > 0,
        "vendors_assessed": s.query(models.Vendor).count(),
        "committees": s.query(models.Committee).count(),
    }


class IncidentForm(BaseModel):
    incident_type: str = "ai_model"   # ai_model | cyber | personal_data_breach
    severity: str = "medium"
    description: str
    model_version: str | None = None
    reported_to: str = "AI/Model Risk Committee"
    report_deadline: str | None = None


@app.post("/api/v1/governance/incidents")
def report_incident(form: IncidentForm):
    """FREE-AI AI incident-reporting mechanism (Part 27.1)."""
    s = models.get_session()
    inc = models.Incident(**form.model_dump())
    s.add(inc)
    s.commit()
    _audit(s, "incident-form", "create", f"incident#{inc.id}")
    return {"incident_id": inc.id, "status": inc.status, "reported_to": inc.reported_to}


@app.get("/api/v1/governance/{artifact_type}")
def get_artifacts(artifact_type: str, request: Request):
    # Declared AFTER the specific /governance/* routes so it doesn't shadow them.
    model = ARTIFACTS.get(artifact_type)
    if model is None:
        raise HTTPException(404, f"unknown artifact_type '{artifact_type}'. "
                                 f"Try: {', '.join(ARTIFACTS)}")
    s = models.get_session()
    rows = [_row(o) for o in s.query(model).all()]
    actor = request.headers.get("x-user", "dashboard")
    _audit(s, actor, "read", artifact_type)
    READS.labels(artifact_type).inc()
    return {"artifact_type": artifact_type, "count": len(rows), "records": rows}


@app.get("/api/v1/go-live")
def go_live():
    """PLATFORM-41: the DB-backed go/no-go gate (Part 34.6)."""
    s = models.get_session()
    if s.query(models.GoLiveTick).count() == 0:
        raise HTTPException(503, "governance DB not seeded; run `make seed-governance`")
    return checklist.render(checklist.resolve(s), checklist.threat_intel_handoff())


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
