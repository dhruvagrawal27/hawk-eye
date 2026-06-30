"""Typology: ghost / insider loan + inflated appraisal (SLOW lane) — DATA-9.

Blueprint Part 12 coverage map (l.417-419), Part 21.1. Signals embedded:
- appraiser == borrower (self-appraisal / conflict),
- thin documentation + inflated appraised value,
- disbursement to a NON-SANCTIONED account.
Surfaces over weeks/months (slow lane); injected with ground truth.
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np

from data.config import LANE_SLOW, make_id
from data.schemas import Linkage, ObjectRef
from data.sim.population import Employee
from data.sim.scenarios._common import Trace, fraud_label, make_event, pick

SCENARIO_ID = "ghost_loan_appraisal"
LANE = LANE_SLOW


def inject(rng: np.random.Generator, population: list[Employee], base_ts) -> Trace:
    appraiser = pick(rng, population, "appraiser")
    officer = pick(rng, population, "loan_officer", exclude={appraiser.employee_id})
    loan_case = make_id("account", "loan", appraiser.employee_id, base_ts.isoformat())
    sanctioned_acct = make_id("account", "sanctioned", loan_case)
    diversion_acct = make_id("account", "diversion", appraiser.employee_id)  # non-sanctioned
    out: Trace = []

    # appraiser appraises their OWN application (appraiser == borrower) with inflated value
    t0 = base_ts.replace(hour=15, minute=0, second=0)
    appraise = make_event(
        appraiser, "submit_appraisal", t0, rng,
        obj=ObjectRef(account_id=loan_case, table="thin_docs", amount=30_000_000, currency="INR"),
        # borrower == appraiser: encode borrower identity in linkage.customer_account
        linkage=Linkage(customer_account=loan_case, maker_id=appraiser.employee_id,
                        checker_id=appraiser.employee_id),
        nonce=0,
    )
    out.append((appraise, fraud_label(appraise, SCENARIO_ID, appraiser.employee_id, LANE)))

    # disbursement to a NON-sanctioned account (diversion_acct != sanctioned_acct)
    t1 = t0 + timedelta(days=14)
    disburse = make_event(
        officer, "disburse_loan", t1, rng,
        obj=ObjectRef(account_id=diversion_acct, amount=30_000_000, currency="INR"),
        # carry both the sanctioned ref and the actual (diverging) destination
        linkage=Linkage(customer_account=sanctioned_acct, maker_id=officer.employee_id),
        nonce=1,
    )
    out.append((disburse, fraud_label(disburse, SCENARIO_ID, appraiser.employee_id, LANE)))
    return out
