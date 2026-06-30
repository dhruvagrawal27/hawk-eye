#!/usr/bin/env python3
"""Capacity forecast tool (PLATFORM-31, blueprint Part 30.2 + Part 34.2).

Projects infra capacity forward from growth inputs (reuses the PLATFORM-5 sizing model) and
emits the per-year sizing + cost trajectory. Feeds the annual capacity assessment that the
IT Strategy Committee (ITSC) reviews (an explicit ITGRCA requirement, Part 30.2).

CLI:
    python capacity_forecast.py --txns-per-day 30000000 --growth 0.35 --years 3
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "sizing"))
from sizing_calculator import size  # noqa: E402


def forecast(txns_per_day: int, growth: float, years: int, telemetry: float = 12.0) -> list[dict]:
    out = []
    t = txns_per_day
    for yr in range(years + 1):
        s = size(t, telemetry)
        out.append({
            "year": yr,
            "txns_per_day": int(t),
            "events_per_day": s.events_per_day,
            "kafka_brokers": s.kafka_brokers,
            "flink_task_managers": s.flink_task_managers,
            "clickhouse_shards": s.clickhouse_shards,
            "redis_gb": s.redis_gb,
            "gpu_pool": s.gpu_count,
            "lightsail_monthly_usd": s.lightsail_monthly_usd["TOTAL"],
            "aws_vpc_monthly_usd": s.aws_monthly_usd["TOTAL"],
        })
        t *= (1 + growth)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Capacity forecast (Part 30.2 / 34.2)")
    ap.add_argument("--txns-per-day", type=int, default=30_000_000)
    ap.add_argument("--growth", type=float, default=0.35, help="YoY growth fraction")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    fc = forecast(a.txns_per_day, a.growth, a.years)
    if a.json:
        print(json.dumps(fc, indent=2))
        return 0
    print(f"Capacity forecast — {a.txns_per_day:,} txns/day, {int(a.growth*100)}% YoY, {a.years}y")
    print(f"{'yr':>3} {'txns/day':>14} {'kafka':>6} {'flink':>6} {'ch_shards':>10} "
          f"{'gpu':>4} {'lightsail$':>11} {'vpc$':>9}")
    for r in fc:
        print(f"{r['year']:>3} {r['txns_per_day']:>14,} {r['kafka_brokers']:>6} "
              f"{r['flink_task_managers']:>6} {r['clickhouse_shards']:>10} {r['gpu_pool']:>4} "
              f"{r['lightsail_monthly_usd']:>11,.0f} {r['aws_vpc_monthly_usd']:>9,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
