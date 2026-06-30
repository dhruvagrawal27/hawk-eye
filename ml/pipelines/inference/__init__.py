"""Serving pipelines (ML-18; blueprint Part 18).

* :mod:`sync_fastlane`  — synchronous L2/L3 fast lane (trees in the hot path).
* :mod:`async_l4_l5`    — async L4/L5 that UPGRADE an existing alert (never block).
* :mod:`schedules`      — cadence constants (L4 15min-hourly, L5 hourly-daily, slow-lane).
* :mod:`backfill`       — ClickHouse-backfill re-scoring (ClickHouse source stubbed).
* :mod:`shadow`         — shadow scoring (challenger scores live traffic, emits NO alerts).
"""

from __future__ import annotations

from ml.pipelines.inference.async_l4_l5 import (
    AlertUpgrade,
    AsyncUpgrader,
    run_async_upgrade,
)
from ml.pipelines.inference.backfill import (
    BackfillResult,
    ClickHouseSource,
    backfill_rescore,
)
from ml.pipelines.inference.schedules import (
    ASYNC_LAYERS,
    BACKFILL_CADENCE_S,
    CADENCES,
    L4_CADENCE_S,
    L5_CADENCE_S,
    SLOW_LANE_CADENCE_S,
    SYNC_LATENCY_BUDGET_MS,
    SYNC_LAYERS,
    Cadence,
    is_async_layer,
    is_sync_layer,
)
from ml.pipelines.inference.shadow import ShadowResult, ShadowScorer
from ml.pipelines.inference.sync_fastlane import FastLaneScore, SyncFastLane

__all__ = [
    "SyncFastLane",
    "FastLaneScore",
    "AsyncUpgrader",
    "AlertUpgrade",
    "run_async_upgrade",
    "ShadowScorer",
    "ShadowResult",
    "ClickHouseSource",
    "backfill_rescore",
    "BackfillResult",
    "Cadence",
    "CADENCES",
    "is_sync_layer",
    "is_async_layer",
    "SYNC_LATENCY_BUDGET_MS",
    "SYNC_LAYERS",
    "ASYNC_LAYERS",
    "L4_CADENCE_S",
    "L5_CADENCE_S",
    "SLOW_LANE_CADENCE_S",
    "BACKFILL_CADENCE_S",
]
