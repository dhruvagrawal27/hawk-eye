"""Fraud-scenario registry (DATA-9).

Blueprint Part 21.1 #3 (l.797-805), Part 12 coverage map (l.403-425). One module per
typology, each exposing inject(rng, population, base_ts) -> list[(L0Event, Label)].

REGISTRY maps scenario_id -> inject fn (all 12 typologies). LANES maps scenario_id ->
"fast" | "slow" so BACKEND's slow-lane scorer / EWS consumes the right traces.

Status: REAL (synthetic-only, ALERT-ONLY — never blocks anything).
"""
from __future__ import annotations

from typing import Callable

from data.config import LANE_FAST, LANE_SLOW

from . import (
    alert_suppression,
    beneficiary_then_approve,
    bulk_exfil_resignation,
    dormant_takeover,
    fake_vendor,
    ghost_employee_payroll,
    ghost_loan_appraisal,
    maker_checker_ring,
    privilege_self_grant,
    rogue_trader,
    suspense_lapping,
    swift_without_cbs,
)

_MODULES = (
    # fast lane (8)
    beneficiary_then_approve,
    dormant_takeover,
    swift_without_cbs,
    suspense_lapping,
    privilege_self_grant,
    bulk_exfil_resignation,
    maker_checker_ring,
    rogue_trader,
    # slow lane (4)
    fake_vendor,
    ghost_employee_payroll,
    alert_suppression,
    ghost_loan_appraisal,
)

# scenario_id -> inject fn
REGISTRY: dict[str, Callable] = {m.SCENARIO_ID: m.inject for m in _MODULES}
# scenario_id -> lane
LANES: dict[str, str] = {m.SCENARIO_ID: m.LANE for m in _MODULES}

FAST_SCENARIOS = tuple(sid for sid, lane in LANES.items() if lane == LANE_FAST)
SLOW_SCENARIOS = tuple(sid for sid, lane in LANES.items() if lane == LANE_SLOW)

assert len(REGISTRY) == 12, "expected all 12 typologies registered"
assert len(FAST_SCENARIOS) == 8 and len(SLOW_SCENARIOS) == 4
