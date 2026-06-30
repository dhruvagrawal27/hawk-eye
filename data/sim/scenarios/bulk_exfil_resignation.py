"""Typology: bulk exfiltration before resignation (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.803), Part 12, Part 6.3/6.4. A download/export spike inside the
notice-period window, exporting to a personal channel. Actor carries leaver/notice flags.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "bulk_exfil_resignation"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    actor = pick(rng, population, "loan_officer")
    # mark the actor as a leaver in notice period (drives change/HR features)
    actor.leaver_flag = True  # type: ignore[attr-defined]
    out: Trace = []
    # export spike: many large exports to a personal channel over the notice window
    for i in range(6):
        t = (base_ts + timedelta(days=i // 2)).replace(hour=19, minute=30 + i, second=0)
        ev = make_event(
            actor, "export", t, rng, channel="dlp", layer="application",
            obj=ObjectRef(table="customer_pii", amount=None),
            linkage=Linkage(),
            nonce=i,
        )
        # tag the actor's leaver/notice context onto the actor snapshot
        ev.actor.leaver_flag = True
        ev.actor.notice_period = True
        out.append((ev, fraud_label(ev, SCENARIO_ID, actor.employee_id, LANE)))
    return out
