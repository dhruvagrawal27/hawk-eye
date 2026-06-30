"""CFR feed + DAMI-unit support (BACKEND-24, blueprint Part 16).

CFR = Central Fraud Registry. Produces CFR feed entries from confirmed-fraud cases. DAMI = Data
Analytics & Market Intelligence unit — aggregate analytics over the case population. SCAFFOLD: live
CFR submission absent; logic runs REAL on synthetic data.
"""

from __future__ import annotations


def cfr_entry(case: dict) -> dict:
    return {
        "cfr_id": f"cfr_{case['alert_id'].replace('alr_', '')}",
        "entity_id": case["entity_id"],
        "amount_inr": int(case.get("exposure_inr", 0)),
        "category": case.get("category", "others"),
        "reported_ts": case.get("created_ts", ""),
    }


def generate_feed(confirmed_fraud_cases: list[dict], *, submission_enabled: bool = False) -> dict:
    items = [cfr_entry(c) for c in confirmed_fraud_cases]
    return {"submission_enabled": submission_enabled, "items": items, "count": len(items)}


def dami_summary(cases: list[dict]) -> dict:
    """DAMI-unit aggregate analytics (counts + exposure by typology) over the case population."""
    by_category: dict[str, int] = {}
    exposure: dict[str, int] = {}
    for c in cases:
        cat = c.get("category", "others")
        by_category[cat] = by_category.get(cat, 0) + 1
        exposure[cat] = exposure.get(cat, 0) + int(c.get("exposure_inr", 0))
    return {
        "total_cases": len(cases),
        "by_category": by_category,
        "exposure_by_category_inr": exposure,
        "total_exposure_inr": sum(exposure.values()),
    }
