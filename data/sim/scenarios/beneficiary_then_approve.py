"""Typology: new-beneficiary-then-high-value-approve (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.798), Part 12, Part 24.5(d). A maker creates a brand-new
beneficiary off-hours and the same isolated maker/checker pair approves a high-value
payment to it minutes later.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "beneficiary_then_approve"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    maker = pick(rng, population, "ops_maker")
    checker = pick(rng, population, "ops_checker", exclude={maker.employee_id})
    ben_id = make_id("beneficiary", maker.employee_id, base_ts.isoformat())
    acct = make_id("account", "victim", maker.employee_id)

    # off-hours creation at ~02:14
    t0 = base_ts.replace(hour=2, minute=14, second=7)
    e0 = make_event(
        maker, "create_beneficiary", t0, rng, maker_checker="maker",
        obj=ObjectRef(beneficiary_id=ben_id, account_id=acct, currency="INR"),
        linkage=Linkage(maker_id=maker.employee_id, customer_account=acct),
        nonce=1,
    )
    # high-value approval ~27 min later by the checker
    t1 = t0 + timedelta(minutes=19, seconds=3)
    e1 = make_event(
        checker, "approve_payment", t1, rng, maker_checker="checker",
        obj=ObjectRef(beneficiary_id=ben_id, account_id=acct, amount=4_800_000, currency="INR"),
        linkage=Linkage(maker_id=maker.employee_id, checker_id=checker.employee_id,
                        customer_account=acct),
        nonce=2,
    )
    return [
        (e0, fraud_label(e0, SCENARIO_ID, maker.employee_id, LANE)),
        (e1, fraud_label(e1, SCENARIO_ID, checker.employee_id, LANE)),
    ]
