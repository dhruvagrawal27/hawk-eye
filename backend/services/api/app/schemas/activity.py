"""Ambient / sub-threshold activity contract — the detection funnel + near-miss watchlist."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubThresholdBand(BaseModel):
    label: str  # watch | elevated | low
    min: int
    max: int
    count: int


class WatchlistItem(BaseModel):
    entity_id: str
    score: int = Field(..., ge=0, le=100)
    top_signal: str
    ts: str


class SubThresholdResponse(BaseModel):
    """Everything scored-but-not-alerted (the 'hidden 95%'): the funnel + the near-miss watchlist."""

    total_scored: int
    alerted: int
    sub_threshold: int
    emit_threshold: int = 70
    bands: list[SubThresholdBand] = Field(default_factory=list)
    watchlist: list[WatchlistItem] = Field(default_factory=list)
