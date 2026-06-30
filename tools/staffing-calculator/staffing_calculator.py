#!/usr/bin/env python3
"""Investigator staffing calculator (PLATFORM-39, blueprint Part 33.3 / Part 14).

Derives investigator headcount + shift roster from alert volume, handling time, and SLA —
the binding operational constraint (Part 14: "size the team to the alert volume the
thresholds produce"). Uses **Erlang C** for a defensible queueing estimate, then lays out a
3-shift roster (insider fraud is not 9–5, Part 33.3).

CLI:
    python staffing_calculator.py --alerts-per-day 120 --handling-min 25 --sla-hours 4
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass


def erlang_c(offered_load: float, agents: int) -> float:
    """Probability an arrival must wait (Erlang C). offered_load in Erlangs."""
    if agents <= 0:
        return 1.0
    if offered_load <= 0:
        return 0.0
    if agents <= offered_load:
        return 1.0
    # iterative to avoid factorial overflow
    summation = 0.0
    term = 1.0  # A^0/0!
    for n in range(agents):
        if n > 0:
            term *= offered_load / n
        summation += term
    last = term * offered_load / agents  # A^N/N!
    top = last * (agents / (agents - offered_load))
    return top / (summation + top)


def service_level(offered_load: float, agents: int, target_wait_h: float, aht_h: float) -> float:
    """Fraction served within target_wait (Erlang C SL formula)."""
    if agents <= offered_load:
        return 0.0
    pw = erlang_c(offered_load, agents)
    return 1.0 - pw * math.exp(-(agents - offered_load) * (target_wait_h / aht_h))


@dataclass
class Staffing:
    alerts_per_day: int
    handling_min: float
    sla_hours: float
    coverage_hours: int
    target_service_level: float
    offered_load_erlangs: float
    concurrent_agents_required: int
    achieved_service_level: float
    occupancy: float
    fte_with_shrinkage: int
    roster: dict


def compute(alerts_per_day: int, handling_min: float, sla_hours: float,
            coverage_hours: int = 24, target_sl: float = 0.85,
            shrinkage: float = 0.30, shifts: int = 3) -> Staffing:
    if alerts_per_day <= 0 or handling_min <= 0:
        raise ValueError("alerts_per_day and handling_min must be > 0")
    aht_h = handling_min / 60.0
    arrival_rate = alerts_per_day / coverage_hours          # alerts/hour
    offered_load = arrival_rate * aht_h                     # Erlangs

    agents = max(1, math.ceil(offered_load))
    while service_level(offered_load, agents, sla_hours, aht_h) < target_sl and agents < 1000:
        agents += 1
    achieved = service_level(offered_load, agents, sla_hours, aht_h)
    occupancy = offered_load / agents if agents else 1.0

    # FTE accounts for leave/training/shrinkage across the coverage window + shifts.
    fte = math.ceil(agents * shifts / (1 - shrinkage))
    per_shift = math.ceil(agents)
    roster = {
        "shifts": shifts,
        "concurrent_per_shift": per_shift,
        "shift_pattern": [f"shift-{i+1}" for i in range(shifts)],
        "note": "insider fraud is not 9-5 — full coverage; seniors on high-risk/high-exposure escalation.",
    }
    return Staffing(
        alerts_per_day=alerts_per_day, handling_min=handling_min, sla_hours=sla_hours,
        coverage_hours=coverage_hours, target_service_level=target_sl,
        offered_load_erlangs=round(offered_load, 3),
        concurrent_agents_required=agents, achieved_service_level=round(achieved, 4),
        occupancy=round(occupancy, 3), fte_with_shrinkage=fte, roster=roster,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Investigator staffing calculator (Part 33.3)")
    ap.add_argument("--alerts-per-day", type=int, default=120)
    ap.add_argument("--handling-min", type=float, default=25.0)
    ap.add_argument("--sla-hours", type=float, default=4.0)
    ap.add_argument("--coverage-hours", type=int, default=24)
    ap.add_argument("--target-sl", type=float, default=0.85)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s = compute(a.alerts_per_day, a.handling_min, a.sla_hours, a.coverage_hours, a.target_sl)
    if a.json:
        print(json.dumps(asdict(s), indent=2))
        return 0
    print(f"Staffing — {a.alerts_per_day} alerts/day, {a.handling_min} min handling, "
          f"SLA {a.sla_hours}h, target SL {int(a.target_sl*100)}%")
    print(f"  offered load        : {s.offered_load_erlangs} Erlangs")
    print(f"  concurrent agents   : {s.concurrent_agents_required} (SL {int(s.achieved_service_level*100)}%, "
          f"occupancy {int(s.occupancy*100)}%)")
    print(f"  FTE (w/ shrinkage)  : {s.fte_with_shrinkage} across {s.roster['shifts']} shifts "
          f"({s.roster['concurrent_per_shift']}/shift)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
