"""CPU model-serving stub implementing the KServe/Triton v2 inference protocol.

PLATFORM-3 / §3 stub rule: ships a *dummy* model so the L0->...->alert topology
validates without GPU Triton. ML (ML-*) swaps in the real Triton image (BOM
stack.triton) serving the actual ONNX L2-L6 models; the v2 contract here matches
so nothing downstream changes. Exposes:
  GET  /v2/health/ready | /v2/health/live   -> readiness/liveness (degradation-switch polls this)
  GET  /v2/models/{model}                   -> model metadata
  POST /v2/models/{model}/infer             -> dummy per-layer anomaly score in [0,1]
  GET  /metrics                             -> Prometheus
The dummy score is a deterministic function of the feature vector so behavioural
tests are reproducible (not random).
"""
from __future__ import annotations

import hashlib
import os
import time

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

MODEL_VERSION = os.environ.get("MODEL_VERSION", "dummy-onnx-0.0.1")
app = FastAPI(title="hawk-eye serving stub (KServe v2)", version=MODEL_VERSION)

INFER = Counter("serving_infer_total", "inference requests", ["model"])
LAT = Histogram("serving_infer_latency_seconds", "inference latency", ["model"])


class InferInput(BaseModel):
    name: str
    shape: list[int] = []
    datatype: str = "FP32"
    data: list[float] = []


class InferRequest(BaseModel):
    inputs: list[InferInput] = []
    id: str | None = None


@app.get("/v2/health/ready")
def ready():
    return {"ready": True}


@app.get("/v2/health/live")
def live():
    return {"live": True}


@app.get("/v2/models/{model}")
def meta(model: str):
    return {
        "name": model,
        "versions": [MODEL_VERSION],
        "platform": "onnxruntime_onnx",
        "inputs": [{"name": "features", "datatype": "FP32", "shape": [-1]}],
        "outputs": [{"name": "score", "datatype": "FP32", "shape": [1]}],
    }


def _dummy_score(model: str, vec: list[float]) -> float:
    """Deterministic pseudo-score in [0,1]. Monotonic-ish in feature magnitude so
    directional/behavioural tests (Part 31.1) are meaningful, salted by model name."""
    if vec:
        mag = sum(abs(x) for x in vec) / (len(vec) or 1)
        base = 1.0 - (1.0 / (1.0 + mag))  # squashes large magnitudes toward 1
    else:
        base = 0.5
    salt = int(hashlib.sha256(model.encode()).hexdigest(), 16) % 100 / 1000.0
    return round(min(1.0, max(0.0, base + salt)), 4)


@app.post("/v2/models/{model}/infer")
def infer(model: str, req: InferRequest):
    start = time.perf_counter()
    INFER.labels(model).inc()
    vec = req.inputs[0].data if req.inputs else []
    score = _dummy_score(model, vec)
    LAT.labels(model).observe(time.perf_counter() - start)
    return {
        "model_name": model,
        "model_version": MODEL_VERSION,
        "id": req.id,
        "outputs": [{"name": "score", "datatype": "FP32", "shape": [1], "data": [score]}],
    }


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
