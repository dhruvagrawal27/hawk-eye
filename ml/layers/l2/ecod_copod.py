"""Parameter-free tail-probability detectors: ECOD + COPOD (L2; blueprint §20.2).

Both are parameter-free (PyOD as-is). When PyOD is absent, ECOD is implemented from
scratch as a numpy empirical-CDF tail probability: for each feature value, take the
smaller of the left-tail CDF P(X<=x) and right-tail CDF P(X>=x), and aggregate the
anomaly score as the sum of negative log tail-probabilities across features (the ECOD
construction). COPOD's fallback reuses the same per-feature tail engine (COPOD differs
mainly by modelling the empirical copula; the tail-aggregation here is a faithful
parameter-free stand-in).
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ml._optional import HAS_PYOD
from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.layers.l2._common import as_matrix


def _empirical_tail_neglogp(train: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Per-feature negative-log tail probability, summed across features (ECOD-style).

    For each column j, fit the empirical left CDF F_l(x)=P(X<=x) and right CDF
    F_r(x)=P(X>=x) from ``train``; the per-feature outlier contribution is
    ``-log(min(F_l, F_r))`` evaluated at the query value. Summing across features gives
    the aggregate anomaly score (higher = more anomalous). Returns an (n_query,) score.
    """
    n_train = train.shape[0]
    n_q, n_feat = query.shape
    eps = 1.0 / (n_train + 1.0)  # Laplace-smoothed floor so log is finite
    contrib = np.zeros((n_q, n_feat), dtype=float)
    for j in range(n_feat):
        col = np.sort(train[:, j])
        q = query[:, j]
        # left tail: fraction of train <= q ; right tail: fraction of train >= q
        left = np.searchsorted(col, q, side="right") / n_train
        right = (n_train - np.searchsorted(col, q, side="left")) / n_train
        tail = np.minimum(left, right)
        tail = np.clip(tail, eps, 1.0)
        contrib[:, j] = -np.log(tail)
    return contrib.sum(axis=1)


class _TailDetector(BaseDetector):
    """Shared base for ECOD/COPOD: parameter-free, PyOD when present, numpy fallback."""

    layer = "L2"
    _pyod_cls_name = "ECOD"

    def __init__(self, *, name: str, version: str = "0.1.0") -> None:
        super().__init__(name=name, version=version)
        self._model: Any = None
        self._train: Optional[np.ndarray] = None
        self._feature_names: list[str] = []

    def _make_pyod(self):  # pragma: no cover - trivial dispatch
        if self._pyod_cls_name == "ECOD":
            from pyod.models.ecod import ECOD

            return ECOD()
        from pyod.models.copod import COPOD

        return COPOD()

    def fit(self, X: Any, y: Optional[Any] = None) -> "_TailDetector":
        mat, names = as_matrix(X)
        self._feature_names = names
        if HAS_PYOD:
            self._model = self._make_pyod()
            self._model.fit(mat)
        else:  # pragma: no cover - sklearn/numpy fallback path
            self._train = mat
        self._fitted = True
        return self

    def _raw_scores(self, X: Any) -> np.ndarray:
        mat, _ = as_matrix(X)
        if HAS_PYOD:
            return np.asarray(self._model.decision_function(mat), dtype=float)
        assert self._train is not None  # pragma: no cover
        return _empirical_tail_neglogp(self._train, mat)  # pragma: no cover

    def score_samples(self, X: Any) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError(f"{type(self).__name__} must be fit before scoring")
        return normalize_scores(self._raw_scores(X), method="rank")

    def explain(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Per-feature tail-probability contributions for the top_k worst features."""
        mat, names = as_matrix(X)
        if HAS_PYOD and self._model is not None:
            train = getattr(self._model, "X_train_", None)
            base = np.asarray(train, dtype=float) if train is not None else mat
        else:  # pragma: no cover
            base = self._train if self._train is not None else mat
        per_feat = _per_feature_tail(base, mat)
        return _top_k_reasons(per_feat, names, top_k)


def _per_feature_tail(train: np.ndarray, query: np.ndarray) -> np.ndarray:
    """(n_query, n_feat) per-feature negative-log tail probabilities."""
    n_train = max(train.shape[0], 1)
    n_q, n_feat = query.shape
    eps = 1.0 / (n_train + 1.0)
    out = np.zeros((n_q, n_feat), dtype=float)
    for j in range(n_feat):
        col = np.sort(train[:, j])
        q = query[:, j]
        left = np.searchsorted(col, q, side="right") / n_train
        right = (n_train - np.searchsorted(col, q, side="left")) / n_train
        tail = np.clip(np.minimum(left, right), eps, 1.0)
        out[:, j] = -np.log(tail)
    return out


def _top_k_reasons(per_feat: np.ndarray, names: list[str], top_k: int) -> list[list[ReasonCode]]:
    reasons: list[list[ReasonCode]] = []
    for row in per_feat:
        total = float(row.sum()) or 1.0
        order = np.argsort(row)[::-1][:top_k]
        rcs = [
            ReasonCode(
                source="shap",
                feature=names[j],
                detail="empirical tail-probability outlier contribution",
                contribution=float(row[j] / total),
            )
            for j in order
            if row[j] > 0
        ]
        reasons.append(rcs)
    return reasons


class EcodDetector(_TailDetector):
    """ECOD (Empirical-CDF Outlier Detection), parameter-free."""

    _pyod_cls_name = "ECOD"

    def __init__(self, *, name: str = "l2_ecod", version: str = "0.1.0") -> None:
        super().__init__(name=name, version=version)


class CopodDetector(_TailDetector):
    """COPOD (Copula-based Outlier Detection), parameter-free."""

    _pyod_cls_name = "COPOD"

    def __init__(self, *, name: str = "l2_copod", version: str = "0.1.0") -> None:
        super().__init__(name=name, version=version)
