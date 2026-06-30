"""Synchronous fast lane: L2 + L3 in the hot path (ML-18; blueprint Part 18).

Trees only (IsolationForest/ECOD ensemble + GBDT) so the per-event latency stays in the
5-30ms budget. Produces a per-entity fused fast-lane score + the L2/L3 sub-scores and a
``model_version`` for each layer (persisted alongside the score by ``ml.pipelines.repro``).

ALERT-ONLY: this returns scores; it never blocks or auto-acts.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.pipelines.inference.schedules import SYNC_LATENCY_BUDGET_MS


@dataclass
class FastLaneScore:
    entity_id: str
    fast_score: float
    l2_score: float
    l3_score: float
    model_versions: dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0
    blocked: bool = False  # ALWAYS False — fast lane never blocks.

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "fast_score": round(self.fast_score, 6),
            "l2_score": round(self.l2_score, 6),
            "l3_score": round(self.l3_score, 6),
            "model_versions": self.model_versions,
            "latency_ms": round(self.latency_ms, 3),
            "blocked": self.blocked,
        }


class SyncFastLane:
    """Score L2 (unsupervised) + L3 (GBDT) synchronously and fuse (max) — alert-only."""

    def __init__(self, l2_detector: Any, l3_scorer: Any, *, fuse: str = "max") -> None:
        self.l2 = l2_detector
        self.l3 = l3_scorer
        if fuse not in ("max", "mean"):
            raise ValueError("fuse must be 'max' or 'mean'")
        self.fuse = fuse

    def _l2_scores(self, X_entity: pd.DataFrame) -> np.ndarray:
        if self.l2 is None:
            return np.zeros(len(X_entity))
        return np.asarray(self.l2.score_samples(X_entity), dtype=float).ravel()

    def _l3_scores(self, X_event: pd.DataFrame) -> np.ndarray:
        if self.l3 is None:
            return np.zeros(len(X_event))
        return np.asarray(self.l3.predict_proba(X_event), dtype=float).ravel()

    def score(
        self,
        *,
        X_entity: pd.DataFrame,
        X_event: Optional[pd.DataFrame] = None,
        event_entity: Optional[pd.Series] = None,
    ) -> list[FastLaneScore]:
        """Score every entity in ``X_entity`` (L2) and roll up L3 per-event max P(fraud)."""
        t0 = time.perf_counter()
        l2 = self._l2_scores(X_entity)

        # Aggregate per-event L3 probabilities up to the entity (max).
        l3_by_entity = pd.Series(0.0, index=X_entity.index)
        if X_event is not None and event_entity is not None and self.l3 is not None:
            p_evt = pd.Series(self._l3_scores(X_event), index=X_event.index)
            grp = p_evt.groupby(np.asarray(event_entity)).max()
            l3_by_entity = grp.reindex(X_entity.index).fillna(0.0)

        mv = {
            "L2_unsupervised": getattr(self.l2, "model_version", "l2@unknown"),
            "L3_gbdt": getattr(self.l3, "model_version", "l3@unknown"),
        }
        out: list[FastLaneScore] = []
        elapsed = (time.perf_counter() - t0) * 1000.0
        per = elapsed / max(1, len(X_entity))
        for i, eid in enumerate(X_entity.index):
            l2s, l3s = float(l2[i]), float(l3_by_entity.iloc[i])
            fast = max(l2s, l3s) if self.fuse == "max" else 0.5 * (l2s + l3s)
            out.append(FastLaneScore(
                entity_id=str(eid), fast_score=fast, l2_score=l2s, l3_score=l3s,
                model_versions=mv, latency_ms=per, blocked=False,
            ))
        return out

    @staticmethod
    def within_budget(scores: list[FastLaneScore]) -> bool:
        """True iff total fast-lane latency is within the sync budget (Part 18)."""
        return sum(s.latency_ms for s in scores) <= SYNC_LATENCY_BUDGET_MS


__all__ = ["SyncFastLane", "FastLaneScore"]
