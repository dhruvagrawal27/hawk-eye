"""L2 ensemble: fuse 2-3 unsupervised detectors + peer-relative baselines (§20.2, §19.2, §29).

``L2Ensemble`` fits 2-3 detectors (default Isolation Forest + ECOD + AutoEncoder) and
fuses their normalised [0,1] scores (mean by default, ``fuse="max"`` configurable).
A diverse ensemble is an evasion countermeasure (§19.2).

Peer-relative baseline hook (``peer_relative_features``): z-scores each entity's
features against its peer-group mean/std (peer group derivable from a column, else
global). Peer-relative scoring makes the model fairer (§29: compare like-with-like, not
against protected attributes) and harder to evade (§19.2: an attacker can't hide by
matching the global average if they stand out within their own peer group).

``explain`` is aggregated from the AutoEncoder member (per-feature reconstruction error)
when present, so the ensemble carries contestable per-feature reason codes (§29.2).
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.layers.l2.autoencoder import AutoEncoderDetector
from ml.layers.l2.ecod_copod import EcodDetector
from ml.layers.l2.isoforest import IsolationForestDetector


def _default_detectors() -> list[BaseDetector]:
    """Part 20.8 one-screen default: IsolationForest + ECOD + AutoEncoder."""
    return [IsolationForestDetector(), EcodDetector(), AutoEncoderDetector()]


class L2Ensemble(BaseDetector):
    """Fuse 2-3 L2 detectors; peer-relative baseline hook; AE-aggregated explanations."""

    layer = "L2"

    def __init__(
        self,
        detectors: Optional[list[BaseDetector]] = None,
        *,
        fuse: str = "mean",
        peer_group_col: Optional[str] = "actor.peer_group",
        name: str = "l2_ensemble",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        self.detectors = detectors if detectors is not None else _default_detectors()
        if not 2 <= len(self.detectors) <= 3:
            raise ValueError("L2Ensemble fuses 2-3 detectors (blueprint §20.2)")
        if fuse not in ("mean", "max"):
            raise ValueError("fuse must be 'mean' or 'max'")
        self.fuse = fuse
        self.peer_group_col = peer_group_col
        self._feature_names: list[str] = []

    # ------------------------------------------------------------------ #
    # peer-relative baseline hook (§29 fairness, §19.2 evasion resistance) #
    # ------------------------------------------------------------------ #
    @staticmethod
    def peer_relative_features(
        X: pd.DataFrame,
        peer_groups: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        """Z-score each numeric feature against its peer-group mean/std (else global).

        ``peer_groups`` is an entity->group Series aligned to ``X.index``. When omitted,
        every entity shares one global peer group (still a valid z-score baseline). The
        returned frame is the per-entity deviation-from-peers signal that the ensemble
        scores, so anomalies are judged relative to comparable entities, not in absolute
        terms (fairness + evasion resistance).
        """
        if not isinstance(X, pd.DataFrame):
            X = pd.DataFrame(np.asarray(X, dtype=float))
        num = X.select_dtypes(include=[np.number])
        if num.shape[1] == 0:
            num = X.apply(pd.to_numeric, errors="coerce").fillna(0.0)
        if peer_groups is None:
            groups = pd.Series("__global__", index=X.index)
        else:
            groups = peer_groups.reindex(X.index).fillna("__global__").astype(str)
        out = num.copy().astype(float)
        for col in num.columns:
            mean = num[col].groupby(groups).transform("mean")
            std = num[col].groupby(groups).transform("std").replace(0, np.nan)
            # fall back to global std (then 1.0) where a peer group has <2 members
            std = std.fillna(num[col].std()).replace(0, np.nan).fillna(1.0)
            out[col] = (num[col] - mean) / std
        return out.fillna(0.0)

    def peer_groups_from_events(
        self, events: pd.DataFrame, entity_index: pd.Index
    ) -> Optional[pd.Series]:
        """Derive an entity->peer_group Series from raw events (if the column exists)."""
        emp_col = "actor.employee_id"
        if self.peer_group_col is None or self.peer_group_col not in events.columns:
            return None
        if emp_col not in events.columns:
            return None
        mapping = (
            events[[emp_col, self.peer_group_col]]
            .dropna()
            .drop_duplicates(subset=[emp_col])
            .set_index(emp_col)[self.peer_group_col]
        )
        return mapping.reindex(entity_index)

    # ------------------------------------------------------------------ #
    def fit(self, X: Any, y: Optional[Any] = None) -> "L2Ensemble":
        if isinstance(X, pd.DataFrame):
            self._feature_names = [str(c) for c in X.columns]
        for det in self.detectors:
            det.fit(X, y)
        self._fitted = True
        return self

    def _member_scores(self, X: Any) -> np.ndarray:
        cols = [det.score_samples(X) for det in self.detectors]
        return np.column_stack(cols)

    def score_samples(self, X: Any) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("L2Ensemble must be fit before scoring")
        member = self._member_scores(X)
        fused = member.max(axis=1) if self.fuse == "max" else member.mean(axis=1)
        return normalize_scores(fused, method="rank")

    def explain(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Aggregate explanations from the AutoEncoder member (per-feature recon error).

        Falls back to the first member exposing a non-trivial ``explain`` if no AE is
        present, then to the ensemble fused score as a single coarse code.
        """
        ae = next((d for d in self.detectors if isinstance(d, AutoEncoderDetector)), None)
        if ae is not None:
            return ae.explain(X, top_k=top_k)
        for det in self.detectors:
            rcs = det.explain(X, top_k=top_k)
            if any(rcs):
                return rcs
        scores = self.score_samples(X)
        return [
            [ReasonCode(source="shap", feature="l2_ensemble_score",
                        detail="fused L2 anomaly score", contribution=float(s))]
            for s in scores
        ]
