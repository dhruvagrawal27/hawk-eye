"""Narrative contract + audit-memo columns (BACKEND-20-adjacent, blueprint Part 25.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NarrativeResponse(BaseModel):
    """Response of ``POST /narratives/{alert_id}`` — labelled AI-generated, advisory only."""

    alert_id: str
    narrative: str
    provider: Literal["near_ai", "groq", "template"]
    tee_attested: bool
    attestation_id: str | None = None
    model: str | None = None
    ai_generated: bool = Field(True, description="UI must label this as AI-generated (Part 25.7)")


class NarrativeAuditMemo(BaseModel):
    """Persisted audit memo for every generated narrative (Part 25.4 columns)."""

    alert_id: str
    provider: Literal["near_ai", "groq", "template"]
    tee_attested: bool
    attestation_id: str | None
    model: str | None
    prompt_hash: str
    ts: str
