"""M1.5 — grievance HR insider signal: change_hr features + entity-matrix inclusion."""

from __future__ import annotations

import pandas as pd

from data.features import change_hr as ch
from ml.adapters.featurize import entity_level_features


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"actor.employee_id": "EMP-a", "action.verb": "file_grievance",
             "context.ts": "2026-06-01T10:00:00Z"},
            {"actor.employee_id": "EMP-a", "action.verb": "file_grievance",
             "context.ts": "2026-06-20T10:00:00Z"},
            {"actor.employee_id": "EMP-b", "action.verb": "login",
             "context.ts": "2026-06-25T10:00:00Z"},
        ]
    )


def test_grievance_count_from_events():
    s = ch.grievance_count(_frame())
    assert int(s.get("EMP-a", 0)) == 2
    assert "EMP-b" not in s.index  # no grievance → omitted


def test_grievance_recency_days():
    rec = ch.grievance_recency(_frame())
    # ref = latest ts (2026-06-25); EMP-a's last grievance 2026-06-20 → 5 days.
    assert abs(rec["EMP-a"] - 5.0) < 0.01
    assert "EMP-b" not in rec.index


def test_grievance_count_falls_back_to_hr_attribute():
    df = pd.DataFrame(
        [{"actor.employee_id": "EMP-c", "action.verb": "login",
          "context.ts": "2026-06-25T10:00:00Z", "actor.grievance_count": 3}]
    )
    assert int(ch.grievance_count(df).get("EMP-c", 0)) == 3


def test_grievance_in_entity_matrix():
    m = entity_level_features(_frame())
    assert "grievance_count" in m.columns
    assert m.loc["EMP-a", "grievance_count"] == 2
    assert m.loc["EMP-b", "grievance_count"] == 0


def test_empty_frames_are_safe():
    assert ch.grievance_count(pd.DataFrame()).empty
    assert ch.grievance_recency(pd.DataFrame()).empty
