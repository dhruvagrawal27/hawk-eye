"""Typology: dormant-account takeover (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.799), Part 12. Reactivation of a dormant account -> silent
channel/contact enrolment -> drain.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "dormant_takeover"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    actor = pick(rng, population, "teller")
    acct = make_id("account", "dormant", actor.employee_id, base_ts.isoformat())
    link = Linkage(customer_account=acct)

    t0 = base_ts.replace(hour=21, minute=5, second=0)
    e0 = make_event(actor, "reactivate_account", t0, rng,
                    obj=ObjectRef(account_id=acct), linkage=link, nonce=1)
    t1 = t0 + timedelta(minutes=8)
    e1 = make_event(actor, "enroll_channel", t1, rng,
                    obj=ObjectRef(account_id=acct), linkage=link, nonce=2)
    t2 = t1 + timedelta(minutes=12)
    e2 = make_event(actor, "cash_withdrawal", t2, rng,
                    obj=ObjectRef(account_id=acct, amount=950_000, currency="INR"),
                    linkage=link, nonce=3)
    out: Trace = []
    for ev in (e0, e1, e2):
        out.append((ev, fraud_label(ev, SCENARIO_ID, actor.employee_id, LANE)))
    return out
