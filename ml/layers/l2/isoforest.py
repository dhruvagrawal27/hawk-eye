"""Isolation Forest detector (L2 primary; blueprint §20.2).

EXACT defaults (Part 20.2): ``n_estimators=150``, ``max_samples=256``,
``max_features=1.0``, ``contamination='auto'`` (overridable via ``expected_rate``).
Score = average path length (shorter path => more isolated => more anomalous).

Uses **PyOD ``IForest``** when available, else falls back to sklearn
``IsolationForest`` with the same hyperparameters. ``score_samples`` returns
rank-normalised anomaly scores in [0,1] (higher = more anomalous).
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ml._optional import HAS_PYOD
from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.config.seeds import GLOBAL_SEED
from ml.layers.l2._common import as_matrix


class IsolationForestDetector(BaseDetector):
    """Isolation Forest UEBA anomaly detector (PyOD IForest, sklearn fallback)."""

    layer = "L2"

    def __init__(
        self,
        *,
        n_estimators: int = 150,
        max_samples: int | str = 256,
        max_features: float = 1.0,
        expected_rate: float | str = "auto",
        random_state: int = GLOBAL_SEED,
        name: str = "l2_isoforest",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.expected_rate = expected_rate  # 'auto' or a float in (0, 0.5]
        self.random_state = random_state
        self._model: Any = None
        self._backend = "pyod" if HAS_PYOD else "sklearn"
        self._feature_names: list[str] = []
        self._train_scores: Optional[np.ndarray] = None

    # ------------------------------------------------------------------ #
    def fit(self, X: Any, y: Optional[Any] = None) -> "IsolationForestDetector":
        mat, names = as_matrix(X)
        self._feature_names = names
        # max_samples must not exceed n_rows for either backend.
        ms = self.max_samples
        if isinstance(ms, int):
            ms = min(ms, max(1, mat.shape[0]))
        if HAS_PYOD:
            from pyod.models.iforest import IForest

            # PyOD's contamination must be a float (it only sets the internal label
            # threshold, NOT decision_function); map 'auto' to a nominal rate so the
            # raw anomaly scores we consume are identical either way.
            cont = self._contamination()
            pyod_cont = 0.1 if cont == "auto" else float(cont)
            self._model = IForest(
                n_estimators=self.n_estimators,
                max_samples=ms,
                max_features=self.max_features,
                contamination=pyod_cont,
                random_state=self.random_state,
            )
            self._model.fit(mat)
            self._train_scores = np.asarray(self._model.decision_scores_, dtype=float)
        else:  # pragma: no cover - sklearn always present on reference venv
            from sklearn.ensemble import IsolationForest

            self._model = IsolationForest(
                n_estimators=self.n_estimators,
                max_samples=ms,
                max_features=self.max_features,
                contamination=self.expected_rate,
                random_state=self.random_state,
            )
            self._model.fit(mat)
            # sklearn: higher score_samples => more normal; negate for anomaly score.
            self._train_scores = -np.asarray(self._model.score_samples(mat), dtype=float)
        self._fitted = True
        return self

    def _contamination(self) -> float | str:
        if self.expected_rate == "auto":
            return "auto"
        return float(self.expected_rate)

    def _raw_scores(self, X: Any) -> np.ndarray:
        mat, _ = as_matrix(X)
        if HAS_PYOD:
            return np.asarray(self._model.decision_function(mat), dtype=float)
        return -np.asarray(self._model.score_samples(mat), dtype=float)  # pragma: no cover

    def score_samples(self, X: Any) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("IsolationForestDetector must be fit before scoring")
        return normalize_scores(self._raw_scores(X), method="rank")

    def explain(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Coarse reason code: surface the IF anomaly score as a single rule-ish code."""
        scores = self.score_samples(X)
        return [
            [
                ReasonCode(
                    source="shap",
                    feature="isolation_path_length",
                    detail="isolation-forest anomaly score",
                    contribution=float(s),
                )
            ]
            for s in scores
        ]
