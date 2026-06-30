"""Shared helpers for fraud-scenario injectors (DATA-9).

Blueprint Part 21.1 #3 (l.797-805), Part 12 coverage map (l.403-425).
Each scenario module exposes:

    inject(rng, population, base_ts) -> list[tuple[L0Event, Label]]

embedding a labelled fraud trace. These helpers centralise event construction and the
off-hours stamping so each typology module stays focused. Status: REAL (synthetic-only,
ALERT-ONLY — labels mark fraud but nothing is ever blocked).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np

from data.config import is_off_hours, make_id
from data.schemas import Action, Actor, Context, L0Event, Linkage, ObjectRef
from data.schemas.label import Label
from data.sim.population import Employee, by_role

Trace = list[tuple[L0Event, Label]]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pick(rng: np.random.Generator, population: list[Employee], role: str,
         exclude: Optional[set[str]] = None) -> Employee:
    """Pick one employee of a role (falls back to any employee if role absent)."""
    exclude = exclude or set()
    pool = [e for e in by_role(population, role) if e.employee_id not in exclude]
    if not pool:
        pool = [e for e in population if e.employee_id not in exclude] or list(population)
    return pool[int(rng.integers(0, len(pool)))]


def make_event(
    emp: Employee,
    verb: str,
    ts: datetime,
    rng: np.random.Generator,
    *,
    channel: Optional[str] = "cbs",
    maker_checker: Optional[str] = None,
    obj: Optional[ObjectRef] = None,
    linkage: Optional[Linkage] = None,
    layer: Optional[str] = None,
    nonce: int = 0,
) -> L0Event:
    """Build a single L0Event for a scenario actor."""
    off = is_off_hours(ts.hour, ts.weekday())
    if layer is None:
        layer = "database" if channel == "db" else "application"
    eid = make_id("event", emp.employee_id, verb, iso(ts), nonce, int(rng.integers(0, 1_000_000)))
    return L0Event(
        event_id=eid,
        ts=iso(ts),
        actor=Actor(**emp.to_actor_kwargs()),
        action=Action(verb=verb, channel=channel, maker_checker=maker_checker),
        object=obj or ObjectRef(),
        context=Context(
            ts=iso(ts),
            src_ip=f"10.20.{int(rng.integers(0, 255))}.{int(rng.integers(0, 255))}",
            device=f"WS-{int(rng.integers(100, 999))}",
            geo=emp.branch,
            session_id=make_id("session", emp.employee_id, iso(ts)),
            layer=layer,
            is_off_hours=off,
            host=f"host-{emp.branch}" if channel == "db" else None,
        ),
        linkage=linkage or Linkage(),
    )


def fraud_label(
    ev: L0Event,
    scenario_id: str,
    actor_id: str,
    lane: str,
    ring_id: Optional[str] = None,
) -> Label:
    return Label(
        event_id=ev.event_id,
        is_fraud=True,
        scenario_id=scenario_id,
        actor_id=actor_id,
        ring_id=ring_id,
        lane=lane,
        label_source="synthetic",
        confidence=1.0,
    )
