"""Typology: SWIFT-without-CBS (the PNB / LoU mechanism, FAST lane) — DATA-9.

Blueprint Part 21.1 #3 (l.800), Part 12, Part 5.5. An instrument (SWIFT/LoU) message is
sent with NO matching CBS posting. The injected fraud sets linkage.swift_ref but leaves
linkage.cbs_ref unset, so DATA-16's SWIFT<->CBS recon join fires on it.
"""
from __future__ import annotations

import numpy as np

from data.config import LANE_FAST, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "swift_without_cbs"
LANE = LANE_FAST


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    maker = pick(rng, population, "ops_maker")
    swift_ref = make_id("event", "swift", maker.employee_id, base_ts.isoformat())
    t0 = base_ts.replace(hour=3, minute=2, second=0)
    # SWIFT instrument message: swift_ref set, NO cbs_ref -> recon mismatch by design.
    e0 = make_event(
        maker, "send_swift_message", t0, rng, channel="swift",
        obj=ObjectRef(instrument="LoU", amount=85_000_000, currency="INR"),
        linkage=Linkage(swift_ref=swift_ref, cbs_ref=None, maker_id=maker.employee_id),
        nonce=1,
    )
    return [(e0, fraud_label(e0, SCENARIO_ID, maker.employee_id, LANE))]
