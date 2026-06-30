"""Typology: rogue trader (FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.805), Part 12. Three combined signals:
- no-leave-taken streak (actor never goes on leave, hiding the book),
- late / cancelled-then-rebooked trades,
- P&L-vs-mark divergence (reported mark drifts from independent/observed valuation).
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "rogue_trader"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    trader = pick(rng, population, "trader")
    deal = make_id("event", "deal", trader.employee_id, base_ts.isoformat())
    link = Linkage(app_txn_id=deal)
    out: Trace = []

    # 1) no-leave-taken signal: an explicit attendance event marking a long no-leave streak
    t0 = base_ts.replace(hour=8, minute=5, second=0)
    nl = make_event(trader, "no_leave_streak", t0, rng, channel="hr",
                    obj=ObjectRef(), linkage=Linkage(), nonce=1)
    out.append((nl, fraud_label(nl, SCENARIO_ID, trader.employee_id, LANE)))

    # 2) late booking, then cancel + rebook (concealment of losses)
    t1 = base_ts.replace(hour=20, minute=50, second=0)  # late, off-hours booking
    book = make_event(trader, "book_trade", t1, rng, channel="treasury",
                      obj=ObjectRef(instrument="IRS", amount=12_000_000, currency="INR"),
                      linkage=link, nonce=2)
    cancel = make_event(trader, "cancel_trade", t1 + timedelta(minutes=10), rng,
                        channel="treasury",
                        obj=ObjectRef(instrument="IRS", amount=12_000_000, currency="INR"),
                        linkage=link, nonce=3)
    rebook = make_event(trader, "rebook_trade", t1 + timedelta(minutes=15), rng,
                        channel="treasury",
                        obj=ObjectRef(instrument="IRS", amount=9_500_000, currency="INR"),
                        linkage=link, nonce=4)
    for ev in (book, cancel, rebook):
        out.append((ev, fraud_label(ev, SCENARIO_ID, trader.employee_id, LANE)))

    # 3) mismarking: trader's reported mark diverges from the independent/observed valuation
    t2 = base_ts.replace(hour=17, minute=30, second=0)
    mark = make_event(trader, "mark_position", t2, rng, channel="treasury",
                      obj=ObjectRef(instrument="IRS", amount=11_800_000, currency="INR"),
                      linkage=link, nonce=5)
    # observed/independent valuation event carrying a materially lower amount
    indep = make_event(trader, "independent_valuation", t2 + timedelta(minutes=1), rng,
                       channel="treasury",
                       obj=ObjectRef(instrument="IRS", amount=8_900_000, currency="INR"),
                       linkage=link, nonce=6)
    out.append((mark, fraud_label(mark, SCENARIO_ID, trader.employee_id, LANE)))
    out.append((indep, fraud_label(indep, SCENARIO_ID, trader.employee_id, LANE)))
    return out
