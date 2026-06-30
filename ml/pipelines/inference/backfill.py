"""ClickHouse-backfill re-scoring (ML-18; blueprint Part 18).

Periodically re-score historical events from the ClickHouse offline store with the current
model (e.g. after a retrain), so prior days reflect the latest detector. The ClickHouse
source is STUBBED here (DATABASE owns the real ``events`` table); the stub reads a parquet
run dir / an in-memory frame with the SAME interface, so swapping in a real ClickHouse
client later changes nothing for callers.

ALERT-ONLY + reconstructability: each re-score is persisted through
:class:`ml.pipelines.repro.ScoreLedger` with its feature vector + model_version.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.adapters import FeatureSource
from ml.pipelines import repro


class ClickHouseSource:
    """# STUB: DATABASE owns the real ClickHouse ``events`` table.

    Stand-in offline event source for backfill. Wraps a ``FeatureSource`` (or a raw
    events/labels frame) and exposes a ``query_window(start, end)`` that filters by ts,
    matching the shape a real ClickHouse client would return.
    """

    def __init__(self, source: Optional[FeatureSource] = None,
                 events: Optional[pd.DataFrame] = None, ts_col: str = "ts") -> None:
        self.ts_col = ts_col
        if events is not None:
            self._events = events
        elif source is not None:
            self._events = source.events()
        else:
            raise ValueError("provide a FeatureSource or an events DataFrame")

    def query_window(self, start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        df = self._events
        if self.ts_col not in df.columns:
            return df.copy()
        ts = pd.to_datetime(df[self.ts_col], utc=True, errors="coerce")
        mask = pd.Series(True, index=df.index)
        if start is not None:
            mask &= ts >= pd.Timestamp(start, tz="UTC")
        if end is not None:
            mask &= ts <= pd.Timestamp(end, tz="UTC")
        return df[mask].copy()


@dataclass
class BackfillResult:
    n_rescored: int
    model_version: str
    score_records: list[repro.ScoreRecord]
    mean_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_rescored": self.n_rescored,
            "model_version": self.model_version,
            "mean_score": round(self.mean_score, 6),
        }


def backfill_rescore(
    ch: ClickHouseSource,
    scorer: Any,
    featurize_fn,
    *,
    layer: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    ledger: Optional[repro.ScoreLedger] = None,
) -> BackfillResult:
    """Re-score a historical ClickHouse window with ``scorer`` and persist every score.

    ``featurize_fn(events) -> feature DataFrame`` turns the queried events into the model's
    feature matrix (e.g. ``featurize.entity_level_features`` or ``event_level_features``).
    """
    events = ch.query_window(start, end)
    X = featurize_fn(events)
    if X is None or len(X) == 0:
        return BackfillResult(0, getattr(scorer, "model_version", "unknown"), [], 0.0)

    led = ledger or repro.ScoreLedger()
    dset_hash = repro.dataset_hash(events)
    recs = led.record_batch(scorer, X, layer=layer, dset_hash=dset_hash)
    mean_s = float(np.mean([r.score for r in recs])) if recs else 0.0
    return BackfillResult(
        n_rescored=len(recs),
        model_version=getattr(scorer, "model_version", "unknown"),
        score_records=recs,
        mean_score=mean_s,
    )


__all__ = ["ClickHouseSource", "backfill_rescore", "BackfillResult"]
