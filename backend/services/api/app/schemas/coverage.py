"""EWS/RFA coverage + board-KRI contracts (cross-job: FRONTEND [FE-proposed] reports).

Matches frontend/src/lib/types.ts EwsCoverageResponse + KriResponse so the connected dashboard
reporting view renders unchanged. Blueprint Part 24.4 (reporting screen), Part 14 (op/biz metrics).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CoverageIndicator(BaseModel):
    code: str
    label: str
    category: str = "EWS"  # EWS | RFA
    covered: bool = False
    source_layer: str | None = None
    rule_id: str | None = None
    note: str | None = None


class EwsCoverageResponse(BaseModel):
    generated_ts: str
    indicators: list[CoverageIndicator] = Field(default_factory=list)
    covered: int = 0
    total: int = 0


class KriCard(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None
    target: float | None = None
    direction: str | None = None  # higher_is_better | lower_is_better
    status: str | None = None  # ok | warning | breach
    delta: float | None = None


class KriTrendPoint(BaseModel):
    period: str

    model_config = {"extra": "allow"}


class CoverageCell(BaseModel):
    area: str
    covered_pct: float


class KriResponse(BaseModel):
    generated_ts: str
    cards: list[KriCard] = Field(default_factory=list)
    trends: list[KriTrendPoint] = Field(default_factory=list)
    coverage: list[CoverageCell] = Field(default_factory=list)
