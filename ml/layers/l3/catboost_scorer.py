"""L3 CatBoost supervised scorer (ML-4; blueprint Part 20.3 — high-card/imbalance GBDT).

EXACT Part 20.3 CatBoost params: depth in [6,10], learning_rate in [0.03,0.1],
l2_leaf_reg in [3,10], ``auto_class_weights='Balanced'``.

Heavy ``catboost`` import stays INSIDE methods so the module always imports. When CatBoost
is absent the scorer falls back to sklearn ``HistGradientBoostingClassifier``.
``predict_proba`` always returns probabilities in [0,1]. TreeSHAP reason codes via ``treeshap``.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_CATBOOST, optional_import
from ml.base import BaseScorer, ReasonCode
from ml.layers.l3 import imbalance


class CatBoostScorer(BaseScorer):
    """CatBoost binary scorer for L3. Falls back to sklearn HistGradientBoosting."""

    layer = "L3"

    def __init__(
        self,
        *,
        depth: int = 8,
        learning_rate: float = 0.05,
        l2_leaf_reg: float = 5.0,
        n_estimators: int = 1500,
        early_stopping_rounds: int = 50,
        valid_frac: float = 0.2,
        random_state: int = 1405,
        name: str = "l3_catboost",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        self.depth = int(np.clip(depth, 6, 10))
        self.learning_rate = float(np.clip(learning_rate, 0.03, 0.1))
        self.l2_leaf_reg = float(np.clip(l2_leaf_reg, 3.0, 10.0))
        self.n_estimators = int(np.clip(n_estimators, 1000, 3000))
        self.early_stopping_rounds = int(early_stopping_rounds)
        self.valid_frac = float(valid_frac)
        self.random_state = int(random_state)

        self._model = None
        self._backend = "catboost" if HAS_CATBOOST else "sklearn"
        self._feature_names: list[str] = []
        self.best_iteration_: Optional[int] = None

    def fit(self, X, y) -> "CatBoostScorer":
        X = _as_frame(X)
        self._feature_names = [str(c) for c in X.columns]
        yarr = imbalance._as_label_array(y)
        if self._backend == "catboost":
            self._fit_catboost(X, yarr)
        else:
            self._fit_sklearn(X, yarr)
        self._fitted = True
        return self

    def _split_valid(self, X: pd.DataFrame, yarr: np.ndarray):
        n = len(X)
        cut = max(1, int(round(n * (1.0 - self.valid_frac))))
        cut = min(cut, n - 1) if n > 1 else n
        if yarr[cut:].sum() == 0 or yarr[cut:].sum() == (n - cut):
            return X, yarr, None, None
        return X.iloc[:cut], yarr[:cut], X.iloc[cut:], yarr[cut:]

    def _fit_catboost(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        cb = optional_import("catboost")
        X_tr, y_tr, X_va, y_va = self._split_valid(X, yarr)
        model = cb.CatBoostClassifier(
            depth=self.depth,
            learning_rate=self.learning_rate,
            l2_leaf_reg=self.l2_leaf_reg,
            n_estimators=self.n_estimators,
            auto_class_weights="Balanced",
            eval_metric="PRAUC",
            random_seed=self.random_state,
            allow_writing_files=False,
            verbose=False,
        )
        if X_va is not None:
            model.fit(
                X_tr,
                y_tr,
                eval_set=(X_va, y_va),
                early_stopping_rounds=self.early_stopping_rounds,
                verbose=False,
            )
            self.best_iteration_ = model.get_best_iteration()
        else:
            model.fit(X, yarr, verbose=False)
        self._model = model

    def _fit_sklearn(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(
            max_iter=self.n_estimators,
            learning_rate=self.learning_rate,
            max_depth=self.depth,
            l2_regularization=self.l2_leaf_reg,
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
            raise RuntimeError("CatBoostScorer must be fit before predict_proba")
        X = _as_frame(X, self._feature_names)
        p = self._model.predict_proba(X)[:, 1]
        return np.clip(np.asarray(p, dtype=float).ravel(), 0.0, 1.0)

    def reason_codes(self, X, top_k: int = 5) -> list[list[ReasonCode]]:
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
