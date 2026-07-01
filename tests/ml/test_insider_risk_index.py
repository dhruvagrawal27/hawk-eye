"""M2.1 — continuous per-user insider-risk index composition."""

from __future__ import annotations

import pandas as pd

from ml.pipelines.insider_risk_index import compute_insider_risk_index


def _events() -> pd.DataFrame:
    rows = []
    # EMP-risky: off-hours activity across 3 days (no leave), recent grievance + role change,
    # a granted-but-unexercised entitlement, leaver flag.
    for day in ("2026-06-07", "2026-06-08", "2026-06-09"):
        rows.append(
            {
                "actor.employee_id": "EMP-risky",
                "action.verb": "login",
                "context.ts": f"{day}T02:30:00Z",
                "context.is_off_hours": True,
                "actor.leaver_flag": True,
            }
        )
    rows += [
        {
            "actor.employee_id": "EMP-risky",
            "action.verb": "file_grievance",
            "context.ts": "2026-06-05T02:00:00Z",
            "actor.leaver_flag": True,
        },
        {
            "actor.employee_id": "EMP-risky",
            "action.verb": "role_change",
            "context.ts": "2026-06-04T02:00:00Z",
            "actor.leaver_flag": True,
        },
        {
            "actor.employee_id": "EMP-risky",
            "action.verb": "grant_entitlement",
            "object.entitlement_id": "approve_payment",
            "context.ts": "2026-03-01T02:00:00Z",
            "actor.leaver_flag": True,
        },
    ]
    # EMP-calm: one on-hours login and a taken leave.
    rows += [
        {
            "actor.employee_id": "EMP-calm",
            "action.verb": "login",
            "context.ts": "2026-06-09T10:00:00Z",
            "context.is_off_hours": False,
        },
        {
            "actor.employee_id": "EMP-calm",
            "action.verb": "leave",
            "context.ts": "2026-06-08T10:00:00Z",
            "context.is_off_hours": False,
        },
    ]
    return pd.DataFrame(rows)


def test_composite_in_range_and_has_subscores():
    idx = compute_insider_risk_index(_events(), alerts_30d={"EMP-risky": 4})
    r = idx["EMP-risky"]
    assert 0 <= r.composite <= 100
    for s in (r.hr_score, r.access_score, r.anomaly_score):
        assert 0.0 <= s <= 1.0
    assert r.components and r.top_drivers


def test_risky_outranks_calm_monotonic():
    idx = compute_insider_risk_index(_events(), alerts_30d={"EMP-risky": 4})
    assert idx["EMP-risky"].composite > idx["EMP-calm"].composite


def test_recent_alerts_raise_the_index():
    ev = _events()
    lo = compute_insider_risk_index(ev, alerts_30d={})["EMP-risky"].composite
    hi = compute_insider_risk_index(ev, alerts_30d={"EMP-risky": 5})[
        "EMP-risky"
    ].composite
    assert hi >= lo


def test_empty_events_returns_empty():
    assert compute_insider_risk_index(pd.DataFrame()) == {}


def test_top_drivers_reflect_signals():
    r = compute_insider_risk_index(_events(), alerts_30d={"EMP-risky": 4})["EMP-risky"]
    # a leaver with off-hours + grievance should surface those among the drivers
    assert any(
        d
        in {
            "leaver_or_notice",
            "offhours_score",
            "grievance_recency",
            "recent_alerts_30d",
            "standing_privilege",
        }
        for d in r.top_drivers
    )
