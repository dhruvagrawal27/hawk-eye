"""Serving cadence constants (ML-18; blueprint Part 18).

Trees (L2/L3) run in the synchronous hot path; deep nets (L4/L5) run async off the hot
path and UPGRADE an existing alert (never block). Slow-lane + backfill run on a daily/
weekly cadence. These constants are the single source of truth the schedulers read.
"""

from __future__ import annotations

from dataclasses import dataclass

# Latency budget for the synchronous fast lane (Part 18: e2e ~100-300ms; trees 5-30ms).
SYNC_LATENCY_BUDGET_MS = 300.0

# Cadence ranges (min, max) in SECONDS.
L4_CADENCE_S = (15 * 60, 60 * 60)  # L4: every 15 min .. hourly
L5_CADENCE_S = (60 * 60, 24 * 60 * 60)  # L5: hourly .. daily
SLOW_LANE_CADENCE_S = (24 * 60 * 60, 7 * 24 * 60 * 60)  # slow-lane: daily .. weekly
BACKFILL_CADENCE_S = (24 * 60 * 60, 7 * 24 * 60 * 60)  # ClickHouse re-score backfill

# Which layers are sync (hot path) vs async (upgrade an existing alert).
SYNC_LAYERS = ("L1", "L2", "L3")
ASYNC_LAYERS = ("L4", "L5")


@dataclass(frozen=True)
class Cadence:
    name: str
    min_seconds: int
    max_seconds: int

    @property
    def default_seconds(self) -> int:
        return self.min_seconds


CADENCES = {
    "L4": Cadence("L4", *L4_CADENCE_S),
    "L5": Cadence("L5", *L5_CADENCE_S),
    "slow_lane": Cadence("slow_lane", *SLOW_LANE_CADENCE_S),
    "backfill": Cadence("backfill", *BACKFILL_CADENCE_S),
}


def is_sync_layer(layer: str) -> bool:
    return layer.upper() in SYNC_LAYERS


def is_async_layer(layer: str) -> bool:
    return layer.upper() in ASYNC_LAYERS


__all__ = [
    "SYNC_LATENCY_BUDGET_MS",
    "L4_CADENCE_S",
    "L5_CADENCE_S",
    "SLOW_LANE_CADENCE_S",
    "BACKFILL_CADENCE_S",
    "SYNC_LAYERS",
    "ASYNC_LAYERS",
    "Cadence",
    "CADENCES",
    "is_sync_layer",
    "is_async_layer",
]
