"""Score-history route (BACKEND) — the per-entity risk timeline the ScoreOverTime panel reads.

Served from the score-history store (ClickHouse when enabled, else the in-memory ring the online
stream fills). For an entity with no streamed history yet (e.g. a seeded demo entity), we synthesize
a plausible rising series toward its current alert risk so the panel is never empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.common import Capability
from app.store.alert_store import ALERTS
from app.store.score_history import SCORE_HISTORY

router = APIRouter(tags=["entities"])

THRESHOLD_SCORE = 16  # 0.16032509 fused threshold projected onto 0–100


@router.get("/entities/{entity_id}/score-history")
def get_score_history(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> dict:
    points = SCORE_HISTORY.history(entity_id, limit=80)
    if not points:
        points = _synthesize(entity_id)
    return {"entity_id": entity_id, "points": points, "threshold_score": THRESHOLD_SCORE}


def _synthesize(entity_id: str) -> list[dict]:
    """Ease up to the entity's current max alert risk over 8 weekly points (never-empty panel)."""
    alerts = [a for a in ALERTS.all() if a.entity_id == entity_id]
    current = max((int(a.risk_score) for a in alerts), default=50)
    baseline = max(8, round(current * 0.25))
    now = datetime.now(timezone.utc)
    pts: list[dict] = []
    for i in range(8):
        t = i / 7
        score = round(baseline + (current - baseline) * (t * t))
        ts = (now - timedelta(days=7 * (7 - i))).isoformat()
        pts.append({"ts": ts, "score": int(score)})
    return pts
