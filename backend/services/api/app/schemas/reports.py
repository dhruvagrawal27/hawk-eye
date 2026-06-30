"""Regulatory export contracts: FMR / CRILC (BACKEND-26, blueprint Part 16/24.2).

SCAFFOLD note: the *generators* run REAL on synthetic data; only the live RBI submission
channel is absent. Exports are alert-only evidence packs — never an auto-classification.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FmrLineItem(BaseModel):
    """One Fraud Monitoring Return line (synthetic)."""

    fmr_id: str
    entity_id: str
    alert_id: str | None = None
    category: str = Field(..., description="RBI FMR fraud category (synthetic mapping)")
    amount_inr: int
    detected_ts: str
    rfa_tagged: bool = False
    status: str = "reported"


class FmrReport(BaseModel):
    generated_ts: str
    period: str
    submission_enabled: bool = Field(False, description="SCAFFOLD: live RBI channel absent locally")
    items: list[FmrLineItem] = Field(default_factory=list)
    total_amount_inr: int = 0


class CrilcLineItem(BaseModel):
    """One CRILC line — ₹3-crore / 7-day trigger, 180-day classification window."""

    crilc_id: str
    entity_id: str
    exposure_inr: int
    crosses_3cr: bool
    reporting_due_ts: str = Field(..., description="7-day reporting trigger deadline")
    classification_due_ts: str = Field(..., description="180-day classification window end")
    rfa_tagged: bool = False
    sma_class: str | None = Field(None, description="Special Mention Account class, if applicable")


class CrilcReport(BaseModel):
    generated_ts: str
    submission_enabled: bool = False
    items: list[CrilcLineItem] = Field(default_factory=list)
    total_exposure_inr: int = 0
