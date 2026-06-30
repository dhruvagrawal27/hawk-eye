"""EWS framework integration with CBS (BACKEND-24, blueprint Part 16).

EWS = Early Warning Signals, integrated with CBS and extended to non-credit/digital activity. Maps
the system's rule/typology hits to the RBI EWS indicator taxonomy and reports indicator coverage.
SCAFFOLD: indicators run REAL on synthetic data; the live CBS/EWS feed is absent.
"""

from __future__ import annotations

# Rule/typology code → RBI EWS indicator (synthetic mapping of the EWS indicator list).
EWS_INDICATORS = {
    "NEW_BENEFICIARY_THEN_HIGHVALUE": "EWS-funds-routed-to-new-beneficiary",
    "DORMANT_REACTIVATION_DRAIN": "EWS-sudden-activity-in-dormant-account",
    "SWIFT_CBS_MISMATCH": "EWS-trade-finance-without-underlying",
    "DB_WRITE_WITHOUT_APP_TXN": "EWS-books-manipulation",
    "ENTITLEMENT_SELF_GRANT": "EWS-unauthorised-privilege-change",
    "JUST_UNDER_THRESHOLD": "EWS-structuring-below-threshold",
    "OFF_HOURS_ACTIVITY": "EWS-anomalous-operating-hours",
    "fake_vendor": "EWS-related-party-vendor",
    "ghost_employee": "EWS-payroll-anomaly",
    "alert_suppression": "EWS-control-override-by-watcher",
    "ghost_loan": "EWS-collateral-overvaluation",
}


def indicators_for(reason_codes: list[dict]) -> list[str]:
    out: list[str] = []
    for rc in reason_codes:
        ind = EWS_INDICATORS.get(rc.get("code") or rc.get("typology"))
        if ind and ind not in out:
            out.append(ind)
    return out


def coverage(active_codes: set[str]) -> dict:
    """EWS indicator-coverage summary for the Compliance dashboard."""
    covered = {EWS_INDICATORS[c] for c in active_codes if c in EWS_INDICATORS}
    total = set(EWS_INDICATORS.values())
    return {
        "covered": sorted(covered),
        "uncovered": sorted(total - covered),
        "coverage_ratio": round(len(covered) / len(total), 3) if total else 0.0,
    }
