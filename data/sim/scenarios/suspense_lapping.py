"""Typology: suspense/nostro lapping (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.801), Part 12, Part 6.2. Aging suspense/nostro items where the
SAME actor both posts and reconciles, rolling balances forward (lapping).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "suspense_lapping"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    actor = pick(rng, population, "ops_maker")
    suspense = make_id("account", "suspense", actor.employee_id, base_ts.isoformat())
    link = Linkage(customer_account=suspense, maker_id=actor.employee_id,
                   checker_id=actor.employee_id)  # same person posts AND reconciles
    out: Trace = []
    # several aging items rolled forward over consecutive days by the same operator
    for day in range(3):
        t = (base_ts + timedelta(days=day)).replace(hour=18, minute=40, second=0)
        post = make_event(actor, "post_suspense_item", t, rng,
                          obj=ObjectRef(account_id=suspense, amount=300_000 + day * 50_000,
                                        currency="INR"),
                          linkage=link, nonce=day * 2)
        recon = make_event(actor, "reconcile_suspense_item", t + timedelta(minutes=2), rng,
                           obj=ObjectRef(account_id=suspense, amount=300_000 + day * 50_000,
                                         currency="INR"),
                           linkage=link, nonce=day * 2 + 1)
        out.append((post, fraud_label(post, SCENARIO_ID, actor.employee_id, LANE)))
        out.append((recon, fraud_label(recon, SCENARIO_ID, actor.employee_id, LANE)))
    return out
