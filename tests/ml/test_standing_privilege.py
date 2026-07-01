"""M2.2 — standing-privilege detection (identity_access.standing_privilege)."""

from __future__ import annotations

import pandas as pd

from data.features import identity_access as ia


def test_flags_unexercised_grant_only():
    df = pd.DataFrame(
        [
            # granted approve_payment ~100d before ref, NEVER exercised → standing + never
            {
                "actor.employee_id": "EMP-x",
                "action.verb": "grant_entitlement",
                "object.entitlement_id": "approve_payment",
                "context.ts": "2026-03-01T10:00:00Z",
            },
            # granted export, and exercised recently → NOT standing
            {
                "actor.employee_id": "EMP-x",
                "action.verb": "grant_entitlement",
                "object.entitlement_id": "export",
                "context.ts": "2026-03-01T10:00:00Z",
            },
            {
                "actor.employee_id": "EMP-x",
                "action.verb": "export",
                "context.ts": "2026-06-08T10:00:00Z",
            },
            {
                "actor.employee_id": "EMP-x",
                "action.verb": "login",
                "context.ts": "2026-06-09T10:00:00Z",
            },
        ]
    )
    res = ia.standing_privilege(df, window_days=90, min_grant_age_days=14)
    assert res.loc["EMP-x", "standing_privilege_count"] == 1
    assert res.loc["EMP-x", "never_exercised_entitlements"] == 1
    assert res.loc["EMP-x", "days_since_grant_max"] >= 14


def test_recent_grant_below_min_age_not_standing():
    df = pd.DataFrame(
        [
            {
                "actor.employee_id": "EMP-z",
                "action.verb": "grant_entitlement",
                "object.entitlement_id": "approve_payment",
                "context.ts": "2026-06-08T10:00:00Z",
            },
            {
                "actor.employee_id": "EMP-z",
                "action.verb": "login",
                "context.ts": "2026-06-09T10:00:00Z",
            },
        ]
    )
    res = ia.standing_privilege(df, min_grant_age_days=14)
    assert res.loc["EMP-z", "standing_privilege_count"] == 0  # grant is only 1 day old


def test_revoke_clears_standing_privilege():
    df = pd.DataFrame(
        [
            {
                "actor.employee_id": "EMP-y",
                "action.verb": "grant_entitlement",
                "object.entitlement_id": "approve_payment",
                "context.ts": "2026-03-01T10:00:00Z",
            },
            {
                "actor.employee_id": "EMP-y",
                "action.verb": "revoke_entitlement",
                "object.entitlement_id": "approve_payment",
                "context.ts": "2026-04-01T10:00:00Z",
            },
            {
                "actor.employee_id": "EMP-y",
                "action.verb": "login",
                "context.ts": "2026-06-09T10:00:00Z",
            },
        ]
    )
    res = ia.standing_privilege(df)
    assert res.loc["EMP-y", "standing_privilege_count"] == 0


def test_empty_is_safe():
    assert ia.standing_privilege(pd.DataFrame()).empty
