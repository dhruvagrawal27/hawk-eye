"""L6 alert schema (BACKEND owns — BACKEND.md §2, blueprint Part 24.5b).

Field-for-field match to the sample alert: alert_id, entity_id, risk_score (0–100 int),
severity, confidence (0–1), status, created_ts, contributing_layers, reason_codes, exposure_inr,
sla_due_ts, pii_tokenized. ``pii_tokenized`` must be ``True`` on anything that can leave the
perimeter — raw PII never appears in an alert.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import AlertStatus, ContributingLayer, ReasonSource, Severity


class ReasonCode(BaseModel):
    """One assembled reason — rule provenance, SHAP contribution, or graph/sequence evidence."""

    model_config = ConfigDict(extra="allow")
    source: ReasonSource
    code: str | None = Field(None, description="Rule code, e.g. NEW_BENEFICIARY_THEN_HIGHVALUE")
    feature: str | None = Field(None, description="SHAP feature name")
    contribution: float | None = Field(None, description="SHAP contribution (signed)")
    detail: str | None = Field(None, description="Human-readable evidence (tokenized)")


class Alert(BaseModel):
    """L6 fusion output (Part 24.5b)."""

    model_config = ConfigDict(use_enum_values=True)

    alert_id: str = Field(..., examples=["alr_3d7e22"])
    entity_id: str = Field(..., description="= employee_id", examples=["EMP-7f3a"])
    risk_score: int = Field(..., ge=0, le=100, examples=[87])
    severity: Severity = Field(..., examples=["high"])
    confidence: float = Field(..., ge=0.0, le=1.0, examples=[0.82])
    status: AlertStatus = AlertStatus.OPEN
    created_ts: str = Field(..., examples=["2026-06-30T02:41:55Z"])
    contributing_layers: list[ContributingLayer] = Field(default_factory=list)
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    exposure_inr: int = Field(0, ge=0, description="Integer INR (CONTEXT.md §6)", examples=[4800000])
    sla_due_ts: str | None = Field(None, examples=["2026-07-30T02:41:55Z"])
    pii_tokenized: bool = Field(True, description="Always True on egress; raw PII never in an alert")

    # Internal-only fields (not part of the wire contract; excluded from public payloads).
    assignee: str | None = Field(None, exclude=True, description="Assigned investigator id")
    model_versions: dict[str, str] = Field(
        default_factory=dict, exclude=True, description="Per-layer model_version for reproducibility"
    )
    ring_id: str | None = Field(None, exclude=True)

    @field_validator("risk_score")
    @classmethod
    def _clamp_score(cls, v: int) -> int:
        return max(0, min(100, int(v)))

    @staticmethod
    def example() -> dict:
        return {
            "alert_id": "alr_3d7e22",
            "entity_id": "EMP-7f3a",
            "risk_score": 87,
            "severity": "high",
            "confidence": 0.82,
            "status": "open",
            "created_ts": "2026-06-30T02:41:55Z",
            "contributing_layers": ["L1_rules", "L2_unsupervised", "L3_gbdt", "L5_graph"],
            "reason_codes": [
                {
                    "source": "rule",
                    "code": "NEW_BENEFICIARY_THEN_HIGHVALUE",
                    "detail": "new payee BEN-9b1c paid INR 48,00,000 within 27 min",
                },
                {
                    "source": "rule",
                    "code": "OFF_HOURS_ACTIVITY",
                    "detail": "02:14 IST, outside actor & peer baseline",
                },
                {
                    "source": "shap",
                    "feature": "new_beneficiary_to_payment_latency_min",
                    "contribution": 0.31,
                },
                {
                    "source": "shap",
                    "feature": "maker_checker_pair_frequency_30d",
                    "contribution": 0.22,
                },
                {
                    "source": "graph",
                    "detail": "maker EMP-7f3a + checker EMP-1a09 recur as an isolated pair (ring_id RNG-12)",
                },
            ],
            "exposure_inr": 4800000,
            "sla_due_ts": "2026-07-30T02:41:55Z",
            "pii_tokenized": True,
        }


class AlertPage(BaseModel):
    """Paginated, ranked alert queue (GET /alerts)."""

    items: list[Alert]
    total: int
    limit: int
    offset: int
    next_offset: int | None = None
