"""Degradation switch — FastAPI (PLATFORM-4, blueprint Part 18 + Part 30.1).

The REAL graceful-degradation control plane. Decides full vs L1-rules-only routing
based on ML-serving health (or a forced override), scores events accordingly, and
proves the ALERT-ONLY golden rule (it returns alerts for humans; never an action).

Endpoints:
  GET  /health                 liveness
  GET  /mode                   {mode, ml_serving_healthy, forced}
  POST /score {event,...}       -> {mode, alert|null}
  POST /admin/force {forced}     toggle forced rules-only (audited admin action)
  GET  /metrics                 Prometheus
"""
from __future__ import annotations

import logging
import os
import time

import httpx
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

from . import health, kafka_worker, scoring

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("degradation-switch")

SERVING_INFER_BASE = os.environ.get("SERVING_INFER_BASE", "http://serving:8001/v2/models")
app = FastAPI(title="hawk-eye degradation-switch", version="1.0.0")

SCORED = Counter("degradation_scored_total", "events scored", ["mode"])
ALERTS = Counter("degradation_alerts_total", "alerts raised", ["mode", "severity"])
MODE_G = Gauge("degradation_rules_only", "1 if currently routing rules-only, else 0")


class ScoreRequest(BaseModel):
    event: dict
    layer_scores: dict[str, float] | None = None


class ForceRequest(BaseModel):
    forced: bool
    actor: str = "platform-admin"   # PAM-gated in prod (PLATFORM-15); audited below


@app.on_event("startup")
def _startup() -> None:
    kafka_worker.start()


@app.get("/health")
def health_ep():
    return {"status": "ok", "service": "degradation-switch"}


@app.get("/mode")
def mode_ep():
    mode = health.current_mode()
    MODE_G.set(1 if mode == "rules_only" else 0)
    return {
        "mode": mode,
        "ml_serving_healthy": health.serving_healthy(),
        "forced": health.is_forced(),
    }


def _fetch_layer_scores(event: dict) -> dict[str, float] | None:
    """Best-effort: pull dummy L2/L3 anomaly scores from serving (full mode only)."""
    obj = event.get("object") or {}
    ctx = event.get("context") or {}
    vec = [
        float(obj.get("amount") or 0) / 1_000_000.0,
        1.0 if ctx.get("is_off_hours") else 0.0,
        float((event.get("actor") or {}).get("tenure_days") or 0) / 3650.0,
    ]
    scores: dict[str, float] = {}
    for layer, model in (("L2_unsupervised", "l2_isoforest"), ("L3_gbdt", "l3_gbdt")):
        try:
            r = httpx.post(
                f"{SERVING_INFER_BASE}/{model}/infer",
                json={"inputs": [{"name": "features", "shape": [len(vec)],
                                  "datatype": "FP32", "data": vec}]},
                timeout=2.0,
            )
            scores[layer] = float(r.json()["outputs"][0]["data"][0])
        except Exception:
            return None  # serving hiccup -> caller will degrade to rules_only
    return scores


@app.post("/score")
def score_ep(req: ScoreRequest):
    mode = health.current_mode()
    MODE_G.set(1 if mode == "rules_only" else 0)
    layer_scores = req.layer_scores
    if mode == "full" and layer_scores is None:
        layer_scores = _fetch_layer_scores(req.event)
        if layer_scores is None:
            mode = "rules_only"   # serving became unreachable mid-request: degrade
    alert = scoring.score_event(req.event, mode, layer_scores)
    SCORED.labels(mode).inc()
    if alert:
        ALERTS.labels(mode, alert["severity"]).inc()
    return {"mode": mode, "alert": alert}


@app.post("/admin/force")
def force_ep(req: ForceRequest):
    health.set_forced(req.forced)
    # Audit the privileged admin action (quis custodiet, Part 19.3). Prod -> hawkeye.audit.
    log.info("AUDIT admin.force forced=%s actor=%s ts=%s", req.forced, req.actor, time.time())
    return {"forced": req.forced, "mode": health.current_mode()}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
