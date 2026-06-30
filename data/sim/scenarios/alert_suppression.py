"""Typology: alert suppression by AML watchers (SLOW lane) — DATA-9.

Blueprint Part 12 coverage map (l.416), Part 21.1. One analyst clears a disproportionate
share of alerts, including a reopened-then-cleared pattern (clears, it reopens, they clear
it again). Surfaces over weeks; injected with ground truth.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_SLOW, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "alert_suppression"
LANE = LANE_SLOW


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    analyst = pick(rng, population, "aml_analyst")
    out: Trace = []

    # disproportionate clear rate: this analyst clears many alerts in a short window
    for i in range(8):
        t = (base_ts + timedelta(days=i)).replace(hour=12, minute=0, second=0)
        alert_ref = make_id("alert", analyst.employee_id, i, base_ts.isoformat())
        ev = make_event(
            analyst, "clear_alert", t, rng, channel="dlp",
            obj=ObjectRef(instrument=alert_ref),
            linkage=Linkage(app_txn_id=alert_ref), nonce=i,
        )
        out.append((ev, fraud_label(ev, SCENARIO_ID, analyst.employee_id, LANE)))

    # reopened-then-cleared pattern on a single alert
    reopened = make_id("alert", "reopened", analyst.employee_id, base_ts.isoformat())
    link = Linkage(app_txn_id=reopened)
    t0 = (base_ts + timedelta(days=9)).replace(hour=12, minute=0, second=0)
    clear1 = make_event(analyst, "clear_alert", t0, rng, channel="dlp",
                        obj=ObjectRef(instrument=reopened), linkage=link, nonce=100)
    reopen = make_event(analyst, "reopen_alert", t0 + timedelta(days=1), rng, channel="dlp",
                        obj=ObjectRef(instrument=reopened), linkage=link, nonce=101)
    clear2 = make_event(analyst, "clear_alert", t0 + timedelta(days=2), rng, channel="dlp",
                        obj=ObjectRef(instrument=reopened), linkage=link, nonce=102)
    for ev in (clear1, reopen, clear2):
        out.append((ev, fraud_label(ev, SCENARIO_ID, analyst.employee_id, LANE)))
    return out
