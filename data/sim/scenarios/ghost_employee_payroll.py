"""Typology: ghost employees / payroll fraud (SLOW lane) — DATA-9.

Blueprint Part 12 coverage map (l.415-419), Part 21.1. Signals embedded:
- no tax footprint for the ghost payee,
- duplicated bank details across payees (the ghost shares a real employee's account).
Surfaces over months (slow lane); injected with ground truth.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_SLOW, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "ghost_employee_payroll"
LANE = LANE_SLOW


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    admin = pick(rng, population, "vendor_admin")  # payroll/procurement admin
    # ghost payee with duplicated bank details (shares the admin's own payroll account)
    ghost_id = make_id("employee", "ghost", admin.employee_id, base_ts.isoformat())
    shared_account = admin.bank_account  # duplicated bank details (the tell)
    out: Trace = []

    onboard = make_event(
        admin, "create_payroll_record", base_ts.replace(hour=10, minute=30, second=0), rng,
        channel="hr",
        # table flags missing tax footprint; account carries the duplicated bank details
        obj=ObjectRef(table="payroll_no_tax_footprint", account_id=shared_account),
        linkage=Linkage(customer_account=shared_account, maker_id=admin.employee_id,
                        checker_id=admin.employee_id),
        nonce=0,
    )
    # tag the ghost id onto the beneficiary for graph dedup
    onboard.object.beneficiary_id = ghost_id
    out.append((onboard, fraud_label(onboard, SCENARIO_ID, admin.employee_id, LANE)))

    # monthly salary runs to the ghost, all to the duplicated account
    for i in range(3):
        t = (base_ts + timedelta(days=30 * (i + 1))).replace(hour=9, minute=0, second=0)
        ev = make_event(
            admin, "run_payroll", t, rng, channel="cbs",
            obj=ObjectRef(account_id=shared_account, beneficiary_id=ghost_id,
                          amount=120_000, currency="INR"),
            linkage=Linkage(customer_account=shared_account, maker_id=admin.employee_id),
            nonce=i + 1,
        )
        out.append((ev, fraud_label(ev, SCENARIO_ID, admin.employee_id, LANE)))
    return out
