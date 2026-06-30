"""Windowed feature jobs keyed by employee_id (DATA-4/22).

Blueprint Part 6 engineering note (l.259): sliding/tumbling windowed features
computed per-entity (online via Flink->Redis; offline via ClickHouse with identical
definitions). Status: REAL on the pure-python KeyedWindowJob fallback.

Two reference features (the DATA-4 acceptance check):
  - velocity_1h:   SLIDING 1h count of action events per employee (txn velocity / burst)
  - tumbling_count: TUMBLING 1h event count per employee

Determinism: counts are a pure function of the event-time stream.
"""
from __future__ import annotations

from typing import Iterable

from data.streaming.flink_jobs.base_job import (
    KeyedWindowJob,
    SlidingWindow,
    TumblingWindow,
)

_ONE_HOUR_S = 3600.0


def _count_agg(_key: str, evs: list[dict]) -> int:
    return len(evs)


def velocity_1h(slide_s: float = 60.0) -> KeyedWindowJob:
    """1h sliding-window event velocity per employee_id (Part 6.2 velocity/burst).

    slide_s controls emission cadence; the count covers the trailing 1h window.
    """
    return KeyedWindowJob(
        window=SlidingWindow(size_s=_ONE_HOUR_S, slide_s=slide_s),
        aggregate=_count_agg,
    )


def tumbling_count(size_s: float = _ONE_HOUR_S) -> KeyedWindowJob:
    """Tumbling-window event count per employee_id."""
    return KeyedWindowJob(
        window=TumblingWindow(size_s=size_s),
        aggregate=_count_agg,
    )


def compute_windowed_features(
    stream: Iterable[dict],
    slide_s: float = 60.0,
) -> dict[str, dict[str, int]]:
    """Run both windowed jobs over `stream`; return per-entity latest feature values.

    Returns {employee_id: {"velocity_1h": int, "tumbling_count_1h": int}}.
    Used by DATA-22 to materialize online features and by the DATA-28 Phase-0 path.
    """
    events = list(stream)
    vel = velocity_1h(slide_s=slide_s)
    tmb = tumbling_count()
    vel.run(events)
    tmb.run(events)
    keys = set()
    for ev in events:
        keys.add((ev.get("actor") or {}).get("employee_id", "UNKNOWN"))
    out: dict[str, dict[str, int]] = {}
    for k in keys:
        out[k] = {
            "velocity_1h": int(vel.latest(k)),
            "tumbling_count_1h": int(tmb.latest(k)),
        }
    return out
