"""CRILC generator (BACKEND-24, blueprint Part 16).

CRILC = Central Repository of Information on Large Credits. Reporting trigger: **₹3-crore exposure
/ 7-day** window; **180-day** classification window. SCAFFOLD: the logic runs REAL on synthetic
exposures; only the live RBI CRILC submission channel is absent.
"""

from __future__ import annotations

from regulatory.util import (
    CRILC_CLASSIFICATION_DAYS,
    CRILC_REPORTING_DAYS,
    THREE_CRORE_INR,
    add_days,
)


def crilc_line(exposure: dict) -> dict:
    """Build one CRILC line from an exposure record ``{entity_id, exposure_inr, detected_ts, rfa_tagged?}``."""
    exposure_inr = int(exposure["exposure_inr"])
    detected_ts = exposure["detected_ts"]
    crosses = exposure_inr >= THREE_CRORE_INR
    return {
        "crilc_id": f"crilc_{exposure['entity_id'].lower().replace('-', '')}",
        "entity_id": exposure["entity_id"],
        "exposure_inr": exposure_inr,
        "crosses_3cr": crosses,
        "reporting_due_ts": add_days(detected_ts, CRILC_REPORTING_DAYS),
        "classification_due_ts": add_days(detected_ts, CRILC_CLASSIFICATION_DAYS),
        "rfa_tagged": bool(exposure.get("rfa_tagged", crosses)),
        "sma_class": exposure.get("sma_class"),
    }


def generate(exposures: list[dict], *, submission_enabled: bool = False) -> dict:
    """Generate a CRILC report. Only exposures that cross ₹3 crore are CRILC-reportable."""
    reportable = [e for e in exposures if int(e["exposure_inr"]) >= THREE_CRORE_INR]
    items = [crilc_line(e) for e in reportable]
    return {
        "submission_enabled": submission_enabled,
        "items": items,
        "total_exposure_inr": sum(i["exposure_inr"] for i in items),
    }
