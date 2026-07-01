"""Explanation route (BACKEND-19, blueprint Part 24.2 l.905 / 11).

GET /explanations/{alert_id} → SHAP top features + rule provenance + sequence attention + graph
evidence — exactly the explanation-panel data, defensible for SAR/FMR filing. Assembled from the
alert's reason codes (rule/shap/graph) plus L4-style sequence attention synthesized from the
entity timeline (# STUB: ML LAXCAT attention).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.common import Capability
from app.schemas.explanations import (
    AttentionStep,
    Explanation,
    RuleProvenance,
    ShapFeature,
)
from app.store.alert_store import ALERTS
from app.store.entity_store import ENTITIES
from rules_engine.engine import DEFAULT_ENGINE

router = APIRouter(tags=["explanations"])


@router.get("/explanations/{alert_id}", response_model=Explanation)
def get_explanation(
    alert_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> Explanation:
    alert = ALERTS.get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")

    shap = [
        ShapFeature(feature=rc.feature, contribution=rc.contribution or 0.0)
        for rc in alert.reason_codes
        if rc.source == "shap" and rc.feature
    ]
    provenance = []
    for rc in alert.reason_codes:
        if rc.source == "rule" and rc.code:
            cfg = DEFAULT_ENGINE.get_rule(rc.code)
            provenance.append(
                RuleProvenance(
                    code=rc.code,
                    version=cfg.version if cfg else "1.0.0",
                    detail=rc.detail or "",
                    severity_hint=cfg.severity if cfg else None,
                )
            )
    graph_evidence = [rc.detail for rc in alert.reason_codes if rc.source == "graph" and rc.detail]

    # Sequence attention (L4) synthesized from the entity timeline — heaviest on the high-value step.
    timeline = ENTITIES.get_timeline(alert.entity_id)
    attention = []
    for i, ev in enumerate(timeline):
        weight = 0.8 if (ev.amount_inr or 0) > 0 else 0.4 if ev.lane == "change" else 0.2
        attention.append(AttentionStep(step=i, verb=ev.verb, ts=ev.ts, weight=weight))

    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="explanation.view",
        target=alert.entity_id,
        detail={"alert_id": alert_id},
    )
    return Explanation(
        alert_id=alert_id,
        entity_id=alert.entity_id,
        risk_score=alert.risk_score,
        shap=shap,
        rule_provenance=provenance,
        sequence_attention=attention,
        graph_evidence=graph_evidence,
        reason_codes=alert.reason_codes,
    )


@router.get("/explanations/{alert_id}/report")
def get_explanation_report(
    alert_id: str,
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> dict:
    """Downloadable, audit-grade explainability report — the full 'why this fired' assembled into one
    structured artifact: score + severity, per-layer contributions (L1→L6), SHAP, rule provenance,
    sequence attention, graph evidence, and the narrative provenance (provider / TEE attestation).
    Alert-only: advisory, a human decides. Suitable for a SAR/FMR evidence pack."""
    from app.schemas.common import iso_z, utcnow

    explanation = get_explanation(alert_id, principal)  # reuses assembly + logs explanation.view
    alert = ALERTS.get(alert_id)
    assert alert is not None  # get_explanation already 404s otherwise
    memos = ALERTS.narrative_memos(alert_id)
    memo = memos[-1] if memos else None

    return {
        "report_type": "alert_explainability_report",
        "schema_version": "1.0",
        "generated_ts": iso_z(utcnow()),
        "alert": {
            "alert_id": alert.alert_id,
            "entity_id": alert.entity_id,
            "risk_score": alert.risk_score,
            "severity": str(alert.severity),
            "confidence": alert.confidence,
            "status": str(alert.status),
            "exposure_inr": alert.exposure_inr,
            "created_ts": alert.created_ts,
            "contributing_layers": alert.contributing_layers,
        },
        "explanation": explanation.model_dump(),
        "narrative_provenance": (
            {
                "provider": memo.provider,
                "model": memo.model,
                "tee_attested": memo.tee_attested,
                "attestation_id": memo.attestation_id,
                "prompt_hash": memo.prompt_hash,
            }
            if memo
            else None
        ),
        "disclaimer": (
            "ALERT-ONLY: an advisory risk explanation, not a determination of fraud. A human "
            "investigator reviews and decides; no action is taken automatically. All PII is tokenized."
        ),
    }
