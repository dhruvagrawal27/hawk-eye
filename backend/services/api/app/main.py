"""Hawk-Eye control-plane API (BACKEND-1, blueprint Part 24.2).

FastAPI app: all routes under ``/api/v1``, JSON-over-HTTPS + mTLS-internal (PLATFORM mesh
terminates), ``GET /health`` + ``GET /metrics`` (Prometheus), structured logging, and a per-request
metrics/access-log middleware. JWT validation is enforced per-route via ``Depends(get_principal)``
so every non-public route 401s without a valid token. ALERT-ONLY: no route auto-blocks or
auto-classifies.

Run (from ``backend/services/api``):  ``uvicorn app.main:app --host 0.0.0.0 --port 8000``
or, from ``backend/``:                ``python run_api.py``
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app.clients.serving_client import SERVING_CLIENT
from app.config import settings
from app.observability.logging import configure_logging, get_logger
from app.observability.metrics import CONTENT_TYPE_LATEST, render_latest, track_request
from app.pii import crypto
from app.routes import api_router
from app.store.seed import seed_demo
from app.stream.engine import STREAM
from app.stream.ws_routes import stream_router, ws_router
from reliability.degradation import DEGRADATION

log = get_logger("hawkeye.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    seed_demo()  # synthetic demo data (worked-burst alert + entity-360)
    if settings.stream_mode == "kafka":
        await STREAM.start_kafka()  # consume events topic → score → Redis → WS (falls back if down)
    log.info("api.start", extra={"env": settings.env, "base_path": settings.api_base_path})
    yield
    await STREAM.stop_kafka()
    log.info("api.stop")


app = FastAPI(
    title="Hawk-Eye Control Plane",
    description="Insider & privileged-user fraud detection — FastAPI control plane (ALERT-ONLY).",
    version="0.1.0",
    openapi_url=f"{settings.api_base_path}/openapi.json",
    docs_url=f"{settings.api_base_path}/docs",
    redoc_url=f"{settings.api_base_path}/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def observe(request: Request, call_next):
    """Per-request metrics + structured access log with a correlation id."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    # Use the route template (not the raw path) to keep metric cardinality bounded.
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    track_request(request.method, path, response.status_code, duration)
    log.info(
        "http.access",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


# --- public ops endpoints (no JWT) ---
@app.get("/health", tags=["ops"])
def health() -> dict:
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": app.version,
        "env": settings.env,
        "base_path": settings.api_base_path,
        "mtls_internal": settings.mtls_internal,
        "auth_mode": settings.auth_mode,
        "serving_ready": SERVING_CLIENT.ready(),
        "degraded_l1_only": DEGRADATION.degraded,
        "pii": crypto.at_rest_status(),
        "alert_only": True,  # invariant: never auto-blocks, never auto-classifies
    }


@app.get("/metrics", tags=["ops"])
def metrics() -> Response:
    return Response(content=render_latest(), media_type=CONTENT_TYPE_LATEST)


# --- realtime stream: WS at root (/ws/alerts) + control under /api/v1/stream ---
app.include_router(ws_router)
app.include_router(stream_router, prefix=settings.api_base_path)

# --- the /api/v1 surface ---
app.include_router(api_router, prefix=settings.api_base_path)
