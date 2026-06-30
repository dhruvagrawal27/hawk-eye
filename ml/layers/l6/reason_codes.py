"""L6 reason-code assembler (ML-7; blueprint Part 20.7, BACKEND.md §2).

Combines rule provenance + SHAP top features + attention/graph evidence into ONE
ranked reason-code list per entity, in the BACKEND.md §2 shape, and builds the L6 Alert.
One alert per entity (fusion reduces alert fatigue).
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional, Sequence

from ml.base.interfaces import Alert, ReasonCode, Severity, severity_from_score

# Rules first (deterministic, regulator-facing), then graph, attention, shap.
_SOURCE_PRIORITY = {"rule": 0, "graph": 1, "attention": 2, "shap": 3}


def _key(rc: ReasonCode) -> tuple:
    return (rc.source, rc.code, rc.feature, rc.detail)


def assemble_reason_codes(
    layer_reason_codes: dict[str, Sequence[ReasonCode]], *, max_codes: int = 6
) -> list[ReasonCode]:
    """Merge per-layer reason codes, dedup, and rank (rules first, then |contribution|)."""
    seen: set = set()
    merged: list[ReasonCode] = []
    for codes in layer_reason_codes.values():
        for rc in codes or []:
            k = _key(rc)
            if k in seen:
                continue
            seen.add(k)
            merged.append(rc)

    def rank(rc: ReasonCode) -> tuple:
        return (_SOURCE_PRIORITY.get(rc.source, 9), -abs(rc.contribution or 0.0))

    merged.sort(key=rank)
    return merged[:max_codes]


def _now_iso() -> str:
    # Date.now() is unavailable in some sandboxes; fall back to a fixed marker if so.
    try:
        return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # pragma: no cover
        return "1970-01-01T00:00:00Z"


def build_alert(
    *,
    alert_id: str,
    entity_id: str,
    calibrated_prob: float,
    confidence: float,
    contributing_layers: Sequence[str],
    reason_codes: Sequence[ReasonCode],
    exposure_inr: Optional[int] = None,
    created_ts: Optional[str] = None,
    sla_days: int = 30,
) -> Alert:
    """Assemble the BACKEND.md §2 alert from fused score + reason codes (alert-only)."""
    risk = int(round(calibrated_prob * 100))
    severity = severity_from_score(risk)
    created = created_ts or _now_iso()
    sla_due = None
    try:
        sla_due = (_dt.datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ")
                   + _dt.timedelta(days=sla_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # pragma: no cover
        sla_due = None
    return Alert(
        alert_id=alert_id,
        entity_id=entity_id,
        risk_score=risk,
        severity=severity.value,
        confidence=round(float(confidence), 4),
        status="open",
        created_ts=created,
        contributing_layers=list(contributing_layers),
        reason_codes=list(reason_codes),
        exposure_inr=exposure_inr,
        sla_due_ts=sla_due,
        pii_tokenized=True,
    )
