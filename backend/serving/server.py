"""Model-serving HTTP surface (BACKEND-9, blueprint Part 18.1/18.3).

A standalone ONNX-Runtime/Triton-shaped service (port 8001 per CONTEXT.md §7). The Rust hot-path
gateway and the Python online path call ``POST /score``; each response carries the per-layer 0–1
scores and the ``model_version`` that produced them (persisted for reproducibility). Run with::

    uvicorn serving.server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from serving.registry import REGISTRY
from serving.runtime import DEFAULT_RUNTIME

app = FastAPI(title="Hawk-Eye Model Serving", version="0.1.0")


class ScoreRequest(BaseModel):
    feature_vector: dict = Field(default_factory=dict)
    layers: list[str] | None = None
    window_mature: bool = False
    routing_key: str = ""


class ScoreResponse(BaseModel):
    scores: dict[str, float]
    model_versions: dict[str, str]
    degraded_layers: list[str] = Field(default_factory=list)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "ready": DEFAULT_RUNTIME.ready()}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    res = DEFAULT_RUNTIME.score(
        req.feature_vector,
        layers=req.layers,
        window_mature=req.window_mature,
        routing_key=req.routing_key,
    )
    return ScoreResponse(
        scores=res.scores, model_versions=res.model_versions, degraded_layers=res.degraded_layers
    )


@app.get("/models")
def models() -> dict:
    return {
        "models": [
            {
                "model_id": a.model_id,
                "layer": a.layer,
                "version": a.version,
                "stage": a.stage,
                "signed": a.signed_valid,
            }
            for a in REGISTRY.list()
        ]
    }
