"""Typology: maker-checker collusion ring (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.804), Part 12, Part 6.5 (feeds the graph layer). A recurring,
isolated colluding maker/checker pair (or small cluster) sharing a ring_id (RNG-*).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "maker_checker_ring"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    maker = pick(rng, population, "ops_maker")
    checker = pick(rng, population, "ops_checker", exclude={maker.employee_id})
    ring_id = make_id("ring", maker.employee_id, checker.employee_id)
    out: Trace = []
    # the same pair recurs across several payments -> isolated subgraph (the ring)
    for i in range(4):
        t = (base_ts + timedelta(days=i)).replace(hour=11, minute=15, second=0)
        acct = make_id("account", "ring", i, maker.employee_id)
        ben = make_id("beneficiary", "ring", i, maker.employee_id)
        link = Linkage(maker_id=maker.employee_id, checker_id=checker.employee_id,
                       customer_account=acct)
        m = make_event(maker, "initiate_payment", t, rng, maker_checker="maker",
                       obj=ObjectRef(account_id=acct, beneficiary_id=ben,
                                     amount=1_200_000, currency="INR"),
                       linkage=link, nonce=i * 2)
        c = make_event(checker, "approve_payment", t + timedelta(minutes=4), rng,
                       maker_checker="checker",
                       obj=ObjectRef(account_id=acct, beneficiary_id=ben,
                                     amount=1_200_000, currency="INR"),
                       linkage=link, nonce=i * 2 + 1)
        out.append((m, fraud_label(m, SCENARIO_ID, maker.employee_id, LANE, ring_id=ring_id)))
        out.append((c, fraud_label(c, SCENARIO_ID, checker.employee_id, LANE, ring_id=ring_id)))
    return out
