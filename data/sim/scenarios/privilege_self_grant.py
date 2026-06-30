"""Typology: privilege self-grant (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.802), Part 12, Part 6.4. A short-lived entitlement granted to
oneself, timed around a fraudulent approval, then revoked to cover tracks.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "privilege_self_grant"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    actor = pick(rng, population, "sysadmin")
    ent = make_id("audit", "entitlement", actor.employee_id, base_ts.isoformat())
    acct = make_id("account", "target", actor.employee_id)

    t0 = base_ts.replace(hour=22, minute=10, second=0)
    grant = make_event(actor, "grant_entitlement", t0, rng, channel="iam",
                       obj=ObjectRef(entitlement_id=ent),
                       linkage=Linkage(maker_id=actor.employee_id, checker_id=actor.employee_id),
                       nonce=1)
    # use the self-granted right
    t1 = t0 + timedelta(minutes=6)
    use = make_event(actor, "approve_payment", t1, rng, maker_checker="checker",
                     obj=ObjectRef(account_id=acct, amount=2_500_000, currency="INR"),
                     linkage=Linkage(checker_id=actor.employee_id, customer_account=acct),
                     nonce=2)
    # revoke shortly after (short-lived grant)
    t2 = t1 + timedelta(minutes=9)
    revoke = make_event(actor, "revoke_entitlement", t2, rng, channel="iam",
                        obj=ObjectRef(entitlement_id=ent),
                        linkage=Linkage(maker_id=actor.employee_id), nonce=3)
    out: Trace = []
    for ev in (grant, use, revoke):
        out.append((ev, fraud_label(ev, SCENARIO_ID, actor.employee_id, LANE)))
    return out
