#!/usr/bin/env python3
"""FinOps: resource tagging, showback/chargeback, TCO (PLATFORM-39, blueprint Part 34.2).

- Resource tagging policy (cost allocation tags) for the fraud function.
- Showback/chargeback rollup of infra + LLM-API + license costs to the fraud cost centre.
- TCO + build-vs-buy comparison; ties to the sizing calculator (PLATFORM-5).

CLI:
    python finops.py showback
    python finops.py tco --years 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# reuse the sizing/cost model (single source of truth for infra $)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sizing"))
from sizing_calculator import size  # noqa: E402

# Mandatory cost-allocation tags (Part 34.2). Every cloud resource carries these.
REQUIRED_TAGS = {
    "project": "hawk-eye",
    "cost_center": "fraud-risk-management",
    "environment": "{dev|staging|prod}",
    "owner": "platform-sre",
    "data_residency": "in-india",
    "data_classification": "{pii|sensitive|operational}",
}

# Monthly non-infra costs (USD, order-of-magnitude).
LLM_API_MONTHLY = 600  # NEAR AI + Groq tokens (tokenized, bounded by rate limits)
LICENSES_MONTHLY = 0  # all OSS (on-prem stack); commercial = 0 by design
SUPPORT_FTE_MONTHLY = 0  # captured under staffing, not FinOps infra


def showback(txns_per_day: int = 30_000_000, telemetry: float = 12.0) -> dict:
    s = size(txns_per_day, telemetry)
    infra = s.lightsail_monthly_usd["TOTAL"]  # chosen deploy target (ADR-0001)
    infra_vpc = s.aws_monthly_usd["TOTAL"]  # scale-up path
    total = infra + LLM_API_MONTHLY + LICENSES_MONTHLY
    return {
        "cost_center": "fraud-risk-management",
        "deploy_target": "lightsail",
        "monthly": {
            "infra_lightsail": infra,
            "infra_vpc_scaleup": infra_vpc,
            "llm_api": LLM_API_MONTHLY,
            "licenses": LICENSES_MONTHLY,
            "TOTAL_chosen": total,
        },
        "chargeback_to": "fraud-risk-management cost centre",
        "tags": REQUIRED_TAGS,
    }


def tco(years: int = 3, txns_per_day: int = 30_000_000) -> dict:
    sb = showback(txns_per_day)
    monthly = sb["monthly"]["TOTAL_chosen"]
    build = monthly * 12 * years
    # build-vs-buy: a commercial UEBA/insider-fraud platform (illustrative)
    buy_annual = 750_000
    buy = buy_annual * years
    return {
        "years": years,
        "build_on_lightsail_oss": round(build),
        "buy_commercial_platform": buy,
        "verdict": "build" if build < buy else "buy",
        "note": "OSS on-prem stack + escalation discipline (Part 20) keeps build TCO low; "
        "no per-seat license; data stays in-India (Part 16).",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Hawk-Eye FinOps (Part 34.2)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sb = sub.add_parser("showback")
    sb.add_argument("--txns-per-day", type=int, default=30_000_000)
    t = sub.add_parser("tco")
    t.add_argument("--years", type=int, default=3)
    tg = sub.add_parser("tags")  # noqa: F841
    a = ap.parse_args()
    if a.cmd == "showback":
        print(json.dumps(showback(a.txns_per_day), indent=2))
    elif a.cmd == "tco":
        print(json.dumps(tco(a.years), indent=2))
    elif a.cmd == "tags":
        print(json.dumps(REQUIRED_TAGS, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
