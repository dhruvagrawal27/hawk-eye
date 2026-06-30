"""Human-in-the-loop natural-justice gate (PLATFORM-37).

Blueprint Part 15 (SBI v. Rajesh Agarwal — natural justice), Part 16, Part 19.6, Part 29.2.
The software proof of the **ALERT-ONLY** golden rule: a classification enters
`pending_review` and **no fraud classification is acted on until a human approves it** —
and even approval only raises an alert/case for a human; it NEVER auto-blocks money.

Bound to the **DPIA sign-off** (Part 28): the gate refuses to process employee
classifications unless an approved employee-monitoring DPIA exists in the governance DB.
Shows **proportionality + explanation** so the decision is contestable (natural justice).

Endpoints:
  POST /api/v1/classifications                  -> hold pending_review (DPIA-bound)
  GET  /api/v1/classifications?status=           -> review queue
  GET  /api/v1/classifications/{id}              -> detail (proportionality + explanation)
  POST /api/v1/classifications/{id}/decision     -> human approve/reject (alert-only)
  GET  /health, /metrics
"""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

import models  # governance models (DPIA binding); on path in container + conftest

app = FastAPI(title="hawk-eye hitl-gate", version="1.0.0")
CLASSIFICATIONS: dict[str, dict] = {}

PENDING = Gauge("hitl_pending_review", "classifications awaiting human review")
DECISIONS = Counter("hitl_decisions_total", "human decisions", ["decision"])


class Classification(BaseModel):
    alert_id: str
    entity_id: str
    risk_score: int
    severity: str = "medium"
    reason_codes: list[dict] = []
    proportionality: str               # why monitoring this signal is proportionate (Part 15/29.2)
    explanation: str                   # human-readable why-it-flagged
    model_version: str | None = None


class Decision(BaseModel):
    decision: str                      # approve | reject
    reviewer: str
    justification: str


def _dpia_signed_off() -> dict | None:
    """Natural-justice binding: require an approved employee-monitoring DPIA (Part 28)."""
    try:
        s = models.get_session()
        dpia = s.query(models.DPIA).filter(models.DPIA.status == "approved").first()
        if dpia:
            return {"dpia_id": dpia.id, "dpo": dpia.dpo, "approved": str(dpia.approval_date)}
    except Exception:
        return None
    return None


@app.get("/health")
def health():
    return {"status": "ok", "service": "hitl-gate", "alert_only": True}


@app.post("/api/v1/classifications")
def submit(c: Classification):
    dpia = _dpia_signed_off()
    if dpia is None:
        # Cannot process an employee classification without a DPIA sign-off (Part 28).
        raise HTTPException(412, "no approved employee-monitoring DPIA sign-off; "
                                 "cannot process classification (natural-justice binding)")
    cid = "cls_" + uuid.uuid4().hex[:10]
    CLASSIFICATIONS[cid] = {
        "classification_id": cid,
        "status": "pending_review",          # held — never auto-acted (ALERT-ONLY)
        "submitted_ts": time.time(),
        "dpia_binding": dpia,
        "decision": None, "reviewer": None, "reviewed_ts": None,
        **c.model_dump(),
    }
    PENDING.set(sum(1 for v in CLASSIFICATIONS.values() if v["status"] == "pending_review"))
    return {"classification_id": cid, "status": "pending_review",
            "message": "held for human review — no action taken (alert-only)",
            "dpia_binding": dpia}


@app.get("/api/v1/classifications")
def queue(status: str | None = "pending_review"):
    items = [v for v in CLASSIFICATIONS.values() if status is None or v["status"] == status]
    return {"status": status, "count": len(items), "classifications": items}


@app.get("/api/v1/classifications/{cid}")
def detail(cid: str):
    c = CLASSIFICATIONS.get(cid)
    if not c:
        raise HTTPException(404, "no such classification")
    return c


@app.post("/api/v1/classifications/{cid}/decision")
def decide(cid: str, d: Decision):
    c = CLASSIFICATIONS.get(cid)
    if not c:
        raise HTTPException(404, "no such classification")
    if c["status"] != "pending_review":
        raise HTTPException(409, f"already decided: {c['status']}")
    if d.decision not in ("approve", "reject"):
        raise HTTPException(400, "decision must be approve|reject")
    if not d.justification.strip():
        raise HTTPException(400, "a justification is required (natural justice)")
    # Even on approve: the OUTCOME is an alert/case raised for a human — never an auto-block.
    c["status"] = "reviewed_confirmed" if d.decision == "approve" else "reviewed_dismissed"
    c["decision"] = d.decision
    c["reviewer"] = d.reviewer
    c["justification"] = d.justification
    c["reviewed_ts"] = time.time()
    c["outcome"] = ("alert_raised_for_human_action" if d.decision == "approve"
                    else "dismissed_false_positive")
    DECISIONS.labels(d.decision).inc()
    PENDING.set(sum(1 for v in CLASSIFICATIONS.values() if v["status"] == "pending_review"))
    return {"classification_id": cid, "status": c["status"], "outcome": c["outcome"],
            "note": "alert-only: approval raises an alert for human action; money is never auto-blocked"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
