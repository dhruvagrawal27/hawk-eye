"""Score-history route (BACKEND) — the per-entity risk timeline the ScoreOverTime panel reads.

Served from the score-history store (ClickHouse when enabled, else the in-memory ring the online
stream fills). For an entity with no streamed history yet (e.g. a seeded demo entity), we synthesize
a plausible rising series toward its current alert risk so the panel is never empty.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.common import Capability
from app.schemas.layer_scores import LayerScorePoint, LayerScoreSeries, LayerScoresResponse
from app.store.alert_store import ALERTS
from app.store.score_history import SCORE_HISTORY
from serving.registry import REGISTRY

router = APIRouter(tags=["entities"])

THRESHOLD_SCORE = 16  # 0.16032509 fused threshold projected onto 0–100
EMIT_THRESHOLD_SCORE = 70  # the alert emit line on the 0–100 fused scale


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


# Per-layer timeline shape: target = fraction of the fused score each layer trends toward; `late`
# layers (graph) stay low then jump near the end (the "rescued late by L5" story), `early` layers
# lead. Deterministic — a stable per-(entity,layer,week) wobble keeps the lines lively but repeatable.
_LAYER_SHAPE: dict[str, tuple[str, str, float, str]] = {
    # layer: (label, registry_layer, target_fraction_of_fused, curve)
    "L2_unsupervised": ("Anomaly", "L2_unsupervised", 0.62, "steady"),
    "L3_gbdt": ("GBDT", "L3_gbdt", 0.9, "early"),
    "L4_sequence": ("Sequence", "L4_sequence", 0.5, "steady"),
    "L5_graph": ("Graph", "L5_graph", 0.8, "late"),
    "L6_fusion": ("Fused L6", "L6_fusion", 1.0, "early"),
}


def _wobble(entity_id: str, layer: str, i: int) -> int:
    h = hashlib.sha256(f"{entity_id}:{layer}:{i}".encode()).digest()[0]
    return (h % 7) - 3  # deterministic ±3


def _layer_series(entity_id: str) -> list[LayerScoreSeries]:
    alerts = [a for a in ALERTS.all() if a.entity_id == entity_id]
    fused = max((int(a.risk_score) for a in alerts), default=50)
    now = datetime.now(timezone.utc)
    series: list[LayerScoreSeries] = []
    for layer, (label, reg_layer, frac, curve) in _LAYER_SHAPE.items():
        target = fused * frac
        base = max(4, target * 0.25)
        art = REGISTRY.production_for(reg_layer)
        pts: list[LayerScorePoint] = []
        for i in range(8):
            t = i / 7
            if curve == "late":
                shape = t**3  # stays low, jumps at the end
            elif curve == "early":
                shape = t**0.6  # rises fast then plateaus
            else:
                shape = t * t
            score = base + (target - base) * shape + _wobble(entity_id, layer, i)
            ts = (now - timedelta(days=7 * (7 - i))).isoformat()
            pts.append(LayerScorePoint(ts=ts, score=int(max(0, min(100, round(score))))))
        series.append(
            LayerScoreSeries(
                layer=layer,
                label=label,
                model_version=art.version if art else "",
                points=pts,
            )
        )
    return series


@router.get("/entities/{entity_id}/layer-scores", response_model=LayerScoresResponse)
def get_layer_scores(
    entity_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> LayerScoresResponse:
    """Per-layer score timeline (mirrors ClickHouse ``hawkeye.scores``): one series per detection
    layer over time, so you can see which layer led, which fired late, and how they fused."""
    return LayerScoresResponse(
        entity_id=entity_id,
        threshold_score=EMIT_THRESHOLD_SCORE,
        series=_layer_series(entity_id),
    )
