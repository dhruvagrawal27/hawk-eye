"""BACKEND API stub (§3 stub rule). Replaced by the real BACKEND FastAPI image.

Just enough of BACKEND.md §3 for the walking skeleton + integration harness to come
up green and for PLATFORM demos (HITL/degradation/alerts sink) to have an endpoint:
  GET  /health, /metrics
  GET  /api/v1/alerts            in-memory alert queue
  POST /api/v1/alerts            ingest an alert (used by the topology smoke sink)
  POST /api/v1/alerts/{id}/disposition   EDD outcome -> label (alert-only proof)
  GET  /api/v1/rules             L1 rule names (for the degradation demo)
PLATFORM writes NO real rules/fusion logic here — BACKEND owns it (BACKEND.md).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

app = FastAPI(title="hawk-eye BACKEND stub", version="0.0.1-stub")
_ALERTS: dict[str, dict] = {}

L1_RULES = [
    "NEW_BENEFICIARY_THEN_HIGHVALUE", "SWIFT_CBS_MISMATCH", "DB_WRITE_NO_APP_TXN",
    "DORMANT_REACTIVATION", "ENTITLEMENT_SELF_GRANT", "OFF_HOURS_HIGH_VALUE",
    "MAKER_CHECKER_COLLUSION_HINT", "BULK_EXPORT_LEAVER_WINDOW",
]


class Disposition(BaseModel):
    outcome: str  # fraud | false_positive | inconclusive
    notes: str = ""
    evidence_ids: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend-stub"}


@app.get("/api/v1/rules")
def rules():
    return {"rules": L1_RULES, "note": "STUB — BACKEND owns the real BRE/SoD matrix"}


@app.get("/api/v1/alerts")
def list_alerts(status: str | None = None, risk_gte: int = 0):
    items = [a for a in _ALERTS.values()
             if (status is None or a.get("status") == status) and a.get("risk_score", 0) >= risk_gte]
    return {"alerts": sorted(items, key=lambda a: a.get("risk_score", 0), reverse=True)}


@app.post("/api/v1/alerts")
def ingest_alert(alert: dict):
    _ALERTS[alert.get("alert_id", f"alr_{len(_ALERTS)}")] = alert
    return {"ingested": True, "alert_id": alert.get("alert_id")}


@app.post("/api/v1/alerts/{alert_id}/disposition")
def disposition(alert_id: str, d: Disposition):
    a = _ALERTS.get(alert_id, {})
    a["status"] = {"fraud": "confirmed_fraud", "false_positive": "closed_fp",
                   "inconclusive": "inconclusive"}.get(d.outcome, "open")
    _ALERTS[alert_id] = a
    return {"alert_id": alert_id, "status": a["status"], "label_written": True,
            "feedback_queued_for_retraining": True, "audit_id": f"aud_{alert_id[-6:]}"}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
