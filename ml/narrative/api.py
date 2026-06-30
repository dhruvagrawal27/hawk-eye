"""POST /narratives/{alert_id} FastAPI router (ML-13; Part 24.2, 25.5-25.6, BACKEND.md §7).

ML owns the narrate() gateway + this router; BACKEND mounts it. Until BACKEND exists,
``create_app()`` gives a standalone app the ML tests drive directly.
Response shape: {narrative, provider, tee_attested, attestation_id, model}.
"""

from __future__ import annotations

from typing import Any

from ml._optional import require
from ml.narrative.gateway import narrate
from ml.narrative.guardrails import RateLimiter

# A process-wide rate limiter for the endpoint (Part 25.7).
_RATE_LIMITER = RateLimiter(max_calls=30, per_seconds=60.0)


def _response(alert_id: str, alert_ctx: dict[str, Any]) -> dict[str, Any]:
    ctx = dict(alert_ctx or {})
    ctx["alert_id"] = alert_id  # path wins
    result = narrate(ctx, rate_limiter=_RATE_LIMITER)
    # BACKEND.md §7 response shape (plus advisory labelling fields)
    return {
        "narrative": result["narrative"],
        "provider": result["provider"],
        "tee_attested": result["tee_attested"],
        "attestation_id": result["attestation_id"],
        "model": result["model"],
        "ai_generated": result.get("ai_generated", True),
        "advisory": result.get("advisory", True),
    }


def get_router():
    """Return an APIRouter mounting POST /narratives/{alert_id} (BACKEND mounts this)."""
    fastapi = require("fastapi", reason="ML-13 narrative router")
    APIRouter = fastapi.APIRouter
    Body = fastapi.Body

    router = APIRouter(prefix="/api/v1", tags=["narratives"])

    @router.post("/narratives/{alert_id}")
    def post_narrative(
        alert_id: str, alert_ctx: dict = Body(default_factory=dict)
    ) -> dict:  # noqa: ANN001
        return _response(alert_id, alert_ctx)

    return router


def create_app():
    """Standalone FastAPI gateway service (ML owns it; BACKEND proxies to it over HTTP).

    Exposes POST /narrate (the shape BACKEND's NarrativeClient posts: ``{"alert_ctx": {...}}``)
    plus the /api/v1/narratives/{alert_id} router and a /health probe.
    """
    fastapi = require("fastapi", reason="ML-13 narrative app")
    Body = fastapi.Body
    app = fastapi.FastAPI(title="Hawk-Eye ML — Narrative Gateway")
    app.include_router(get_router())

    @app.post("/narrate")
    def narrate_endpoint(payload: dict = Body(default_factory=dict)) -> dict:  # noqa: ANN001
        ctx = payload.get("alert_ctx", payload)
        result = narrate(ctx, rate_limiter=_RATE_LIMITER)
        return {
            "narrative": result["narrative"],
            "provider": result["provider"],
            "tee_attested": result["tee_attested"],
            "attestation_id": result["attestation_id"],
            "model": result["model"],
        }

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "narrative-gateway"}

    return app
