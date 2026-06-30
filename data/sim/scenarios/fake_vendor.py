"""Typology: fake-vendor / billing fraud (SLOW lane) — DATA-9.

Blueprint Part 12 coverage map (l.415-419), Part 21.1. Signals embedded:
- vendor address == the controlling employee's address,
- single-client vendor (only ever bills this org),
- round / sequential invoice numbers.
Surfaces over weeks (slow lane); injected here with ground truth for the slow-lane scorer.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_SLOW, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "fake_vendor"
LANE = LANE_SLOW


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    admin = pick(rng, population, "vendor_admin")
    # vendor whose address == the employee's own address (the tell)
    vendor_id = make_id("vendor", admin.employee_id, base_ts.isoformat())
    out: Trace = []

    create = make_event(
        admin, "create_vendor", base_ts.replace(hour=10, minute=0, second=0), rng,
        obj=ObjectRef(account_id=vendor_id),
        # reuse customer_account to carry the vendor's address-id == employee address_id
        linkage=Linkage(customer_account=admin.address_id, maker_id=admin.employee_id),
        nonce=0,
    )
    out.append((create, fraud_label(create, SCENARIO_ID, admin.employee_id, LANE)))

    # sequential, round invoice numbers over several weeks (single-client vendor)
    base_inv = 1000
    for i in range(4):
        t = (base_ts + timedelta(days=7 * (i + 1))).replace(hour=14, minute=0, second=0)
        inv_no = base_inv + i  # sequential
        ev = make_event(
            admin, "approve_invoice", t, rng,
            obj=ObjectRef(account_id=vendor_id, instrument=f"INV-{inv_no}",
                          amount=500_000, currency="INR"),  # round amount
            linkage=Linkage(customer_account=admin.address_id, maker_id=admin.employee_id,
                            checker_id=admin.employee_id),
            nonce=i + 1,
        )
        out.append((ev, fraud_label(ev, SCENARIO_ID, admin.employee_id, LANE)))
    return out
