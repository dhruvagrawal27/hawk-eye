"""Management analytics contract — fraud-typology prevalence + confirmed-rate (portfolio view)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TypologyStat(BaseModel):
    typology: str  # scenario_id, e.g. "beneficiary_then_approve"
    label: str  # human label
    layers: list[str] = Field(default_factory=list)  # detection layers that catch it (L1..L5)
    alerts: int  # alerts raised for this typology
    confirmed: int  # human-confirmed fraud (disposition = fraud)
    false_positive: int  # human-cleared
    open: int  # still under review
    confirmed_rate: float = Field(..., ge=0.0, le=1.0)  # confirmed / (confirmed + false_positive)
    exposure_inr: int  # total exposure across this typology's alerts


class TypologyTotals(BaseModel):
    alerts: int
    confirmed: int
    false_positive: int
    open: int
    confirmed_rate: float
    exposure_inr: int


class TypologyAnalyticsResponse(BaseModel):
    """Per-typology prevalence + confirmed-rate + exposure, most prevalent first."""

    typologies: list[TypologyStat] = Field(default_factory=list)
    totals: TypologyTotals
