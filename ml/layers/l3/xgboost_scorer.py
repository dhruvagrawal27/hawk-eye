"""L3 XGBoost supervised scorer (ML-4; blueprint Part 20.3 — robust GBDT).

EXACT Part 20.3 XGBoost params: tree_method=hist, max_depth in [4,8], eta in [0.01,0.05],
subsample=0.8, colsample_bytree=0.8, min_child_weight>=5, scale_pos_weight=neg/pos,
eval_metric=aucpr, early stopping.

Heavy ``xgboost`` import stays INSIDE methods so the module always imports. When XGBoost
is absent the scorer falls back to sklearn ``GradientBoostingClassifier``. ``predict_proba``
always returns probabilities in [0,1]. TreeSHAP reason codes via ``treeshap``.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_XGBOOST, optional_import
from ml.base import BaseScorer, ReasonCode
from ml.layers.l3 import imbalance


class XGBoostScorer(BaseScorer):
    """XGBoost binary scorer for L3 (robust GBDT). Falls back to sklearn GradientBoosting."""

    layer = "L3"

    def __init__(
        self,
        *,
        max_depth: int = 6,
        eta: float = 0.03,
        n_estimators: int = 1500,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        min_child_weight: float = 5.0,
        early_stopping_rounds: int = 50,
        valid_frac: float = 0.2,
        random_state: int = 1405,
        name: str = "l3_xgboost",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        self.max_depth = int(np.clip(max_depth, 4, 8))
        self.eta = float(np.clip(eta, 0.01, 0.05))
        self.n_estimators = int(np.clip(n_estimators, 1000, 3000))
        self.subsample = float(subsample)
        self.colsample_bytree = float(colsample_bytree)
        self.min_child_weight = float(max(5.0, min_child_weight))
        self.early_stopping_rounds = int(early_stopping_rounds)
        self.valid_frac = float(valid_frac)
        self.random_state = int(random_state)

        self._model = None
        self._backend = "xgboost" if HAS_XGBOOST else "sklearn"
        self._feature_names: list[str] = []
        self.best_iteration_: Optional[int] = None

    def _params(self, y) -> dict:
        return dict(
            tree_method="hist",
            max_depth=self.max_depth,
            eta=self.eta,
            learning_rate=self.eta,
            n_estimators=self.n_estimators,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            min_child_weight=self.min_child_weight,
            scale_pos_weight=imbalance.scale_pos_weight(y),
            eval_metric="aucpr",
            objective="binary:logistic",
            random_state=self.random_state,
            n_jobs=-1,
            verbosity=0,
        )

    def fit(self, X, y) -> "XGBoostScorer":
        X = _as_frame(X)
        self._feature_names = [str(c) for c in X.columns]
        yarr = imbalance._as_label_array(y)
        if self._backend == "xgboost":
            self._fit_xgboost(X, yarr)
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

    def _fit_xgboost(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        xgb = optional_import("xgboost")
        params = self._params(yarr)
        X_tr, y_tr, X_va, y_va = self._split_valid(X, yarr)
        if X_va is not None:
            # early_stopping_rounds moved to the constructor in xgboost>=2.0.
            try:
                model = xgb.XGBClassifier(
                    early_stopping_rounds=self.early_stopping_rounds, **params
                )
                model.fit(X_tr, y_tr, eval_set=[(X_va, y_va)], verbose=False)
            except TypeError:  # pragma: no cover - very old xgboost
                model = xgb.XGBClassifier(**params)
                model.fit(
                    X_tr,
                    y_tr,
                    eval_set=[(X_va, y_va)],
                    early_stopping_rounds=self.early_stopping_rounds,
                    verbose=False,
                )
            self.best_iteration_ = getattr(model, "best_iteration", None)
        else:
            model = xgb.XGBClassifier(**params)
            model.fit(X, yarr)
        self._model = model

    def _fit_sklearn(self, X: pd.DataFrame, yarr: np.ndarray) -> None:
        from sklearn.ensemble import GradientBoostingClassifier

        model = GradientBoostingClassifier(
            n_estimators=min(self.n_estimators, 400),
            learning_rate=self.eta,
            max_depth=self.max_depth,
            subsample=self.subsample,
            n_iter_no_change=self.early_stopping_rounds,
            validation_fraction=max(0.1, self.valid_frac),
            random_state=self.random_state,
        )
        # GradientBoostingClassifier has no class weight -> use balanced sample weights.
        model.fit(X, yarr, sample_weight=imbalance.sample_weight(yarr))
        self._model = model
        self.best_iteration_ = getattr(model, "n_estimators_", None)

    def predict_proba(self, X) -> np.ndarray:
        if not self._fitted or self._model is None:
            raise RuntimeError("XGBoostScorer must be fit before predict_proba")
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
