"""L3 LightGBM supervised scorer (ML-4; blueprint Part 20.3 — DEFAULT GBDT).

EXACT Part 20.3 LightGBM params: objective=binary, metric=average_precision (LightGBM
exposes it as ``average_precision``; falls back to ``auc``), num_leaves in [31,255],
max_depth=-1, learning_rate in [0.02,0.05], n_estimators 1000-3000 WITH early stopping,
feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, min_child_samples in [50,200],
``is_unbalance=True`` (or ``scale_pos_weight=neg/pos``).

The heavy ``lightgbm`` import stays INSIDE methods so the module always imports. When
LightGBM is absent the scorer transparently falls back to sklearn
``HistGradientBoostingClassifier`` (also histogram-based GBDT), so ``predict_proba``
always returns real probabilities in [0,1].

Live reason codes come from plain TreeSHAP (``treeshap.tree_shap_reason_codes``); NO
interaction values on the hot path (blueprint Part 18/20.6).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_LIGHTGBM, require
from ml.base import BaseScorer, ReasonCode
from ml.layers.l3 import imbalance


class LightGBMScorer(BaseScorer):
    """LightGBM binary scorer for L3 (default GBDT). Falls back to sklearn HistGBDT."""

    layer = "L3"

    def __init__(
        self,
        *,
        num_leaves: int = 63,
        max_depth: int = -1,
        learning_rate: float = 0.03,
        n_estimators: int = 1500,
        feature_fraction: float = 0.8,
        bagging_fraction: float = 0.8,
        bagging_freq: int = 1,
        min_child_samples: int = 100,
        use_scale_pos_weight: bool = False,
        early_stopping_rounds: int = 50,
        valid_frac: float = 0.2,
        random_state: int = 1405,
        name: str = "l3_lightgbm",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        # Clamp to the blueprint's documented bands so misconfiguration can't drift out.
        self.num_leaves = int(np.clip(num_leaves, 31, 255))
        self.max_depth = int(max_depth)
        self.learning_rate = float(np.clip(learning_rate, 0.02, 0.05))
        self.n_estimators = int(np.clip(n_estimators, 1000, 3000))
        self.feature_fraction = float(feature_fraction)
        self.bagging_fraction = float(bagging_fraction)
        self.bagging_freq = int(bagging_freq)
        self.min_child_samples = int(np.clip(min_child_samples, 50, 200))
        self.use_scale_pos_weight = bool(use_scale_pos_weight)
        self.early_stopping_rounds = int(early_stopping_rounds)
        self.valid_frac = float(valid_frac)
        self.random_state = int(random_state)

        self._model: Any = None
        self._backend = "lightgbm" if HAS_LIGHTGBM else "sklearn"
        self._feature_names: list[str] = []
        self.best_iteration_: Optional[int] = None

    # ------------------------------------------------------------------ #
    def _params(self, y) -> dict:
        params = dict(
            objective="binary",
            num_leaves=self.num_leaves,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            n_estimators=self.n_estimators,
            feature_fraction=self.feature_fraction,
            bagging_fraction=self.bagging_fraction,
            bagging_freq=self.bagging_freq,
            min_child_samples=self.min_child_samples,
            random_state=self.random_state,
            n_jobs=-1,
            verbose=-1,
        )
        if self.use_scale_pos_weight:
            params["scale_pos_weight"] = imbalance.scale_pos_weight(y)
        else:
            params["is_unbalance"] = True
        return params

    def fit(self, X, y) -> "LightGBMScorer":  # type: ignore[override]  # intentional: supervised fit requires y
        X = _as_frame(X)
        self._feature_names = [str(c) for c in X.columns]
        yarr = imbalance._as_label_array(y)

        if self._backend == "lightgbm":
            self._fit_lightgbm(X, yarr)
        else:
            self._fit_sklearn(X, yarr)
        self._fitted = True
        return self

    def _split_valid(self, X: pd.DataFrame, yarr: np.ndarray):
        """Index-order (time-aware) holdout: tail of the rows is the early-stopping valid set."""
        n = len(X)
        cut = max(1, int(round(n * (1.0 - self.valid_frac))))
        cut = min(cut, n - 1) if n > 1 else n
        tr = slice(0, cut)
        va = slice(cut, n)
        # Guard: validation set must contain both classes for the metric to be meaningful.
        if yarr[va].sum() == 0 or yarr[va].sum() == (n - cut):
            return X, yarr, None, None
        return X.iloc[tr], yarr[tr], X.iloc[va], yarr[va]

    def _fit_lightgbm(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        lgb = require("lightgbm")
        params = self._params(yarr)
        # average_precision is the blueprint's primary metric; fall back to auc if unsupported.
        metric = "average_precision"
        X_tr, y_tr, X_va, y_va = self._split_valid(X, yarr)
        self._model = lgb.LGBMClassifier(**params)
        if X_va is not None:
            try:
                self._model.set_params(metric=metric)
                self._model.fit(
                    X_tr,
                    y_tr,
                    eval_set=[(X_va, y_va)],
                    eval_metric=metric,
                    callbacks=[
                        lgb.early_stopping(self.early_stopping_rounds, verbose=False),
                        lgb.log_evaluation(0),
                    ],
                )
            except Exception:
                # Some builds reject 'average_precision' as eval_metric -> retry with auc.
                self._model = lgb.LGBMClassifier(**params)
                self._model.set_params(metric="auc")
                self._model.fit(
                    X_tr,
                    y_tr,
                    eval_set=[(X_va, y_va)],
                    eval_metric="auc",
                    callbacks=[
                        lgb.early_stopping(self.early_stopping_rounds, verbose=False),
                        lgb.log_evaluation(0),
                    ],
                )
            self.best_iteration_ = getattr(self._model, "best_iteration_", None)
        else:
            self._model.fit(X, yarr)

    def _fit_sklearn(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        from sklearn.ensemble import HistGradientBoostingClassifier

        X_tr, y_tr, X_va, y_va = self._split_valid(X, yarr)
        model = HistGradientBoostingClassifier(
            max_iter=self.n_estimators,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.num_leaves,
            max_depth=None if self.max_depth < 0 else self.max_depth,
            min_samples_leaf=self.min_child_samples,
            l2_regularization=1.0,
            early_stopping=True,
            n_iter_no_change=self.early_stopping_rounds,
            class_weight="balanced",
            random_state=self.random_state,
        )
        model.fit(X, yarr)
        self._model = model
        self.best_iteration_ = getattr(model, "n_iter_", None)

    def predict_proba(self, X) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise RuntimeError("LightGBMScorer must be fit before predict_proba")
        X = _as_frame(X, self._feature_names)
        p = self._model.predict_proba(X)[:, 1]
        return np.clip(np.asarray(p, dtype=float).ravel(), 0.0, 1.0)

    def reason_codes(self, X, top_k: int = 5) -> list[list[ReasonCode]]:
        """Per-row TreeSHAP reason codes (plain TreeSHAP — never interaction values online)."""
        if not self._fitted or self._model is None:
            return [[] for _ in range(len(X))]
        from ml.layers.l3 import treeshap

        X = _as_frame(X, self._feature_names)
        return treeshap.tree_shap_reason_codes(self._model, X, top_k=top_k)


def _as_frame(X, feature_names: Optional[list[str]] = None) -> pd.DataFrame:
    if isinstance(X, pd.DataFrame):
        return X
    arr = np.asarray(X)
    cols = feature_names if feature_names else [f"f{i}" for i in range(arr.shape[1])]
    return pd.DataFrame(arr, columns=cols)
