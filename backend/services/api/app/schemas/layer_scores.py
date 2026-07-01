"""Per-layer score-timeline contract — one series per detection layer over time.

Mirrors the ClickHouse ``hawkeye.scores`` table (per-event × per-layer × model_version): instead of
one fused line, this exposes how *each* layer's score for an entity evolved — so an investigator can
see, e.g., L3 leading early while L5 (graph) only fires late and lifts the fused score over the bar.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LayerScorePoint(BaseModel):
    ts: str
    score: int = Field(..., ge=0, le=100)


class LayerScoreSeries(BaseModel):
    layer: str  # L2_unsupervised | L3_gbdt | L4_sequence | L5_graph | L6_fusion
    label: str
    model_version: str = ""
    points: list[LayerScorePoint] = Field(default_factory=list)


class LayerScoresResponse(BaseModel):
    entity_id: str
    threshold_score: int
    series: list[LayerScoreSeries] = Field(default_factory=list)
