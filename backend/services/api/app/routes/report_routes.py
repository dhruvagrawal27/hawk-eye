"""Regulatory export routes (BACKEND-26, blueprint Part 24.2 l.912 / 16).

GET /reports/fmr and GET /reports/crilc — Compliance-only CRILC/FMR-ready exports, consumed by
FRONTEND and stored by DATABASE. FMR is generated only from human-confirmed fraud (alert-only /
natural justice). SCAFFOLD: ``submission_enabled`` reflects that the live RBI channel is absent.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.audit.writer import AUDIT
from app.auth.deps import require_role
from app.auth.principal import Principal
from app.config import settings
from app.schemas.common import AlertStatus, Role, iso_z, utcnow
from app.schemas.reports import CfrReport, CrilcReport, FmrReport
from app.store.alert_store import ALERTS
from regulatory import cfr, crilc, fmr, rfa

router = APIRouter(tags=["reports"])

_COMPLIANCE = require_role(Role.DGM_COMPLIANCE, Role.AGM_VIGILANCE)


def _case(alert) -> dict:
    case = {
        "alert_id": alert.alert_id,
        "entity_id": alert.entity_id,
        "exposure_inr": alert.exposure_inr,
        "created_ts": alert.created_ts,
        "risk_score": alert.risk_score,
        "reason_codes": [rc.model_dump(exclude_none=True) for rc in alert.reason_codes],
    }
    return rfa.tag(case)


@router.get("/reports/fmr", response_model=FmrReport)
def report_fmr(principal: Principal = Depends(_COMPLIANCE)) -> FmrReport:
    confirmed = [
        _case(a) for a in ALERTS.all() if str(a.status) == AlertStatus.CONFIRMED_FRAUD.value
    ]
    report = fmr.generate(confirmed, submission_enabled=settings.rbi_submission_enabled)
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="report.fmr",
        detail={"lines": len(report["items"])},
    )
    return FmrReport(generated_ts=iso_z(utcnow()), **report)


@router.get("/reports/cfr", response_model=CfrReport)
def report_cfr(principal: Principal = Depends(_COMPLIANCE)) -> CfrReport:
    """Central Fraud Registry feed of human-confirmed insider frauds + DAMI aggregate analytics.

    Alert-only / natural justice: a CFR entry exists only after a human ``CONFIRMED_FRAUD``
    disposition. SCAFFOLD: ``submission_enabled`` reflects that the live RBI CFR channel is absent.
    """
    confirmed: list[dict] = []
    for a in ALERTS.all():
        if str(a.status) == AlertStatus.CONFIRMED_FRAUD.value:
            case = _case(a)
            # Category aligned with the FMR mapping so CFR/FMR stay consistent (else 'others').
            case["category"] = fmr.fmr_category(case["reason_codes"])
            confirmed.append(case)
    feed = cfr.generate_feed(confirmed, submission_enabled=settings.rbi_submission_enabled)
    dami = cfr.dami_summary(confirmed)
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="report.cfr",
        detail={"lines": feed["count"]},
    )
    return CfrReport(generated_ts=iso_z(utcnow()), dami_summary=dami, **feed)


@router.get("/reports/crilc", response_model=CrilcReport)
def report_crilc(principal: Principal = Depends(_COMPLIANCE)) -> CrilcReport:
    exposures = [
        {
            "entity_id": a.entity_id,
            "exposure_inr": a.exposure_inr,
            "detected_ts": a.created_ts,
            "rfa_tagged": _case(a)["rfa_tagged"],
        }
        for a in ALERTS.all()
        if a.exposure_inr > 0
    ]
    report = crilc.generate(exposures, submission_enabled=settings.rbi_submission_enabled)
    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="report.crilc",
        detail={"lines": len(report["items"])},
    )
    return CrilcReport(generated_ts=iso_z(utcnow()), **report)
