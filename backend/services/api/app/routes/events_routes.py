"""Synthetic event ingestion (BACKEND-13 entry point).

POST /events/ingest feeds one L0 event through the online topology (rules → serving → fusion) and
returns the emitted alert (or null if deduped / below threshold). The PRODUCTION ingestion entry is
Kafka via the Rust gateway; this HTTP route exists for local/synthetic replay and demos. Requires a
valid token (service accounts carry ``events:write`` scope).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth.deps import get_principal
from app.auth.principal import Principal
from app.pipeline.online import ONLINE
from app.schemas.alerts import Alert
from app.schemas.events import L0Event

router = APIRouter(tags=["ingest"])


@router.post("/events/ingest")
def ingest_event(
    event: L0Event,
    principal: Principal = Depends(get_principal),
    full: bool = Query(False, description="Run full L2/L3 + L6 fusion (no L1 short-circuit)"),
) -> dict:
    alert: Alert | None = ONLINE.process(event.model_dump(), full=full)
    return {
        "ingested": True,
        "event_id": event.event_id,
        "alert": alert.model_dump() if alert else None,
        "alerted": alert is not None,
    }
