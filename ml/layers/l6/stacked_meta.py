"""L6 stacked meta-learner (ML-7; blueprint Part 7/L6, 20.7, 22.2).

A TRANSPARENT stacked meta-model (logistic regression by default, or shallow LightGBM)
over the per-layer scores + L1 rule hits. Transparency matters: the *final* decision must
itself be explainable and auditable. Output is calibrated downstream to 0-100.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from ml._optional import optional_import
from ml.base.interfaces import BaseScorer, ReasonCode

# Canonical per-layer input columns the meta-learner stacks over.
LAYER_COLUMNS = ("L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph")


def assemble_layer_matrix(
    scores: dict[str, Sequence[float]], index=None
) -> pd.DataFrame:
    """Build the meta-learner input frame from a dict of per-layer score vectors.

    Missing layers are filled with 0.0 so the meta-model always sees LAYER_COLUMNS.
    """
    n = len(next(iter(scores.values()))) if scores else 0
    df = pd.DataFrame(index=index if index is not None else range(n))
    for col in LAYER_COLUMNS:
        vals = scores.get(col)
        df[col] = np.asarray(vals, dtype=float) if vals is not None else 0.0
    return df


class StackedMetaLearner(BaseScorer):
    """Transparent stacked fusion over per-layer scores + rule hits."""

    layer = "L6"

    def __init__(self, kind: str = "logistic", version: str = "0.1.0") -> None:
        super().__init__(name="l6_stacked_meta", version=version)
        if kind not in ("logistic", "lightgbm"):
            raise ValueError("kind must be 'logistic' or 'lightgbm'")
        self.kind = kind
        self._model: Any = None
        self._columns: list[str] = list(LAYER_COLUMNS)

    def _build(self):
        if self.kind == "lightgbm":
            lgb = optional_import("lightgbm")
            if lgb is not None:
                return lgb.LGBMClassifier(
                    n_estimators=120,
                    num_leaves=7,
                    max_depth=3,
                    learning_rate=0.05,
                    verbose=-1,
                    class_weight="balanced",
                )
        return LogisticRegression(max_iter=1000, class_weight="balanced")

    def fit(self, X, y=None) -> "StackedMetaLearner":
        Xdf = X if isinstance(X, pd.DataFrame) else assemble_layer_matrix(_as_dict(X))
        self._columns = list(Xdf.columns)
        self._model = self._build()
        self._model.fit(Xdf.to_numpy(dtype=float), np.asarray(y).astype(int).ravel())
        self._fitted = True
        return self

    def predict_proba(self, X) -> np.ndarray:
        Xdf = X if isinstance(X, pd.DataFrame) else assemble_layer_matrix(_as_dict(X))
        Xdf = Xdf.reindex(columns=self._columns, fill_value=0.0)
        proba = self._model.predict_proba(Xdf.to_numpy(dtype=float))
        return (
            proba[:, 1]
            if proba.ndim == 2 and proba.shape[1] > 1
            else np.asarray(proba).ravel()
        )

    def layer_contributions(self, X) -> list[dict[str, float]]:
        """Per-row contribution of each layer (transparent: logistic coef×value, else importance)."""
        Xdf = (
            X if isinstance(X, pd.DataFrame) else assemble_layer_matrix(_as_dict(X))
        ).reindex(columns=self._columns, fill_value=0.0)
        if isinstance(self._model, LogisticRegression):
            coef = self._model.coef_.ravel()
            contrib = Xdf.to_numpy(dtype=float) * coef
        else:  # tree model: importance-weighted feature value
            imp = getattr(
                self._model, "feature_importances_", np.ones(len(self._columns))
            )
            imp = imp / (imp.sum() or 1.0)
            contrib = Xdf.to_numpy(dtype=float) * imp
        return [dict(zip(self._columns, row)) for row in contrib]

    def reason_codes(self, X, top_k: int = 3) -> list[list[ReasonCode]]:
        out: list[list[ReasonCode]] = []
        for contrib in self.layer_contributions(X):
            ranked = sorted(contrib.items(), key=lambda kv: abs(kv[1]), reverse=True)[
                :top_k
            ]
            out.append(
                [
                    ReasonCode(source="shap", feature=k, contribution=float(v))
                    for k, v in ranked
                    if v != 0
                ]
            )
        return out


def _as_dict(X) -> dict[str, Any]:
    if isinstance(X, dict):
        return X
    arr = np.asarray(X, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return {
        LAYER_COLUMNS[i]: arr[:, i]
        for i in range(min(arr.shape[1], len(LAYER_COLUMNS)))
    }
