"""Per-role normal-behaviour generators with diurnal/weekly rhythms (DATA-8).

Blueprint Part 21.1 #2 (l.796). Emits BENIGN labelled-as-clean L0 events:
- tellers active in branch hours,
- DBAs running nightly batch (off-hours but benign),
- ops makers/checkers pairing on payments,
- aml_analysts dispositioning alerts during the day,
- traders/loan_officers/etc. with role-appropriate verbs.

Uses data.config.is_off_hours to stamp Context.is_off_hours. Deterministic from the rng
passed in. Status: REAL (synthetic-only).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from data.config import is_off_hours, make_id
from data.schemas import Action, Actor, Context, L0Event, Linkage, ObjectRef
from data.sim.population import Employee

# Per-role: (active hour range, typical daily event count, verbs, channel).
# Hour ranges are local "branch" hours; weekends are quieter (handled below).
ROLE_PROFILE: dict[str, dict] = {
    "teller":       {"hours": (9, 18), "per_day": 6, "verbs": ["login", "cash_deposit", "cash_withdrawal", "balance_enquiry"], "channel": "cbs"},
    "ops_maker":    {"hours": (9, 19), "per_day": 5, "verbs": ["login", "create_beneficiary", "initiate_payment", "modify_account"], "channel": "cbs"},
    "ops_checker":  {"hours": (9, 19), "per_day": 5, "verbs": ["login", "approve_payment", "verify_beneficiary"], "channel": "cbs"},
    "dba":          {"hours": (1, 5),  "per_day": 4, "verbs": ["login", "db_select", "batch_job", "db_maintenance"], "channel": "db"},
    "sysadmin":     {"hours": (8, 20), "per_day": 4, "verbs": ["login", "grant_entitlement", "config_change", "patch"], "channel": "iam"},
    "loan_officer": {"hours": (9, 18), "per_day": 4, "verbs": ["login", "open_loan_case", "disburse_loan", "review_application"], "channel": "cbs"},
    "appraiser":    {"hours": (9, 18), "per_day": 3, "verbs": ["login", "submit_appraisal", "site_visit"], "channel": "cbs"},
    "trader":       {"hours": (8, 17), "per_day": 7, "verbs": ["login", "book_trade", "amend_trade", "mark_position"], "channel": "treasury"},
    "aml_analyst":  {"hours": (9, 18), "per_day": 8, "verbs": ["login", "open_alert", "clear_alert", "escalate_alert"], "channel": "dlp"},
    "vendor_admin": {"hours": (9, 18), "per_day": 3, "verbs": ["login", "create_vendor", "approve_invoice", "modify_vendor"], "channel": "cbs"},
}

DEFAULT_PROFILE = {"hours": (9, 18), "per_day": 3, "verbs": ["login"], "channel": "cbs"}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _benign_event(
    emp: Employee,
    verb: str,
    ts: datetime,
    rng: np.random.Generator,
    channel: str,
) -> L0Event:
    hour = ts.hour
    weekday = ts.weekday()
    off = is_off_hours(hour, weekday)
    layer = "database" if channel == "db" else "application"
    eid = make_id("event", emp.employee_id, verb, _iso(ts), int(rng.integers(0, 1_000_000)))
    mc = None
    if verb in ("create_beneficiary", "initiate_payment", "modify_account"):
        mc = "maker"
    elif verb in ("approve_payment", "verify_beneficiary"):
        mc = "checker"
    amount = None
    if verb in ("cash_deposit", "cash_withdrawal", "initiate_payment", "disburse_loan", "book_trade"):
        amount = int(rng.integers(1_000, 200_000))  # benign small/medium amounts
    return L0Event(
        event_id=eid,
        ts=_iso(ts),
        actor=Actor(**emp.to_actor_kwargs()),
        action=Action(verb=verb, channel=channel, maker_checker=mc),
        object=ObjectRef(amount=amount, currency="INR" if amount else None),
        context=Context(
            ts=_iso(ts),
            src_ip=f"10.20.{int(rng.integers(0, 255))}.{int(rng.integers(0, 255))}",
            device=f"WS-{int(rng.integers(100, 999))}",
            geo=emp.branch,
            session_id=make_id("session", emp.employee_id, ts.date().isoformat()),
            layer=layer,
            is_off_hours=off,
            host=f"host-{emp.branch}" if channel == "db" else None,
        ),
        linkage=Linkage(maker_id=emp.employee_id if mc == "maker" else None,
                        checker_id=emp.employee_id if mc == "checker" else None),
    )


def day_events_for_employee(
    emp: Employee, day: datetime, rng: np.random.Generator
) -> list[L0Event]:
    """Generate one employee's benign events for a single calendar day."""
    profile = ROLE_PROFILE.get(emp.role, DEFAULT_PROFILE)
    weekday = day.weekday()
    is_weekend = weekday >= 5
    # diurnal/weekly rhythm: fewer events on weekends (DBAs still run nightly batch).
    base = profile["per_day"]
    if is_weekend:
        base = max(1, base // 3) if emp.role == "dba" else int(rng.integers(0, 2))
    n = int(rng.poisson(max(0.1, base)))
    if n == 0:
        return []
    lo, hi = profile["hours"]
    events: list[L0Event] = []
    for _ in range(n):
        # sample an hour within the role's active window with a little jitter
        hour = int(rng.integers(lo, hi)) if hi > lo else lo
        minute = int(rng.integers(0, 60))
        second = int(rng.integers(0, 60))
        ts = day.replace(hour=hour % 24, minute=minute, second=second, microsecond=0)
        verb = profile["verbs"][int(rng.integers(0, len(profile["verbs"])))]
        events.append(_benign_event(emp, verb, ts, rng, profile["channel"]))
    return events


def generate_normal(
    population: list[Employee],
    start: datetime,
    days: int,
    rng: np.random.Generator,
) -> list[L0Event]:
    """Generate benign traffic for the whole population over `days`."""
    events: list[L0Event] = []
    for d in range(days):
        day = start + timedelta(days=d)
        for emp in population:
            events.extend(day_events_for_employee(emp, day, rng))
    return events


def demo() -> list[L0Event]:
    from data.sim.population import demo as pop_demo

    rng = np.random.default_rng(3)
    start = datetime(2026, 1, 5, tzinfo=timezone.utc)  # a Monday
    return generate_normal(pop_demo()[:10], start, 2, rng)
