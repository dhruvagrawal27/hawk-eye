"""Shared helpers for L2 detectors: matrix coercion + standardisation.

Kept inside ``ml/layers/l2/`` (stay-in-lane). pandas-3.0-safe: all dtype checks go
through ``pd.api.types.*`` (never ``np.issubdtype`` on a Series dtype).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.base import feature_names_of


def as_matrix(X: Any) -> tuple[np.ndarray, list[str]]:
    """Coerce a feature input (DataFrame / ndarray / list) to a float matrix + names.

    Non-numeric DataFrame columns are coerced with ``pd.to_numeric`` (errors -> NaN),
    then NaN/inf are zero-filled so downstream linear algebra is finite.
    """
    names = feature_names_of(X)
    if isinstance(X, pd.DataFrame):
        cols = []
        for c in X.columns:
            s = X[c]
            if pd.api.types.is_bool_dtype(s):
                s = s.astype(float)
            elif not pd.api.types.is_numeric_dtype(s):
                s = pd.to_numeric(s, errors="coerce")
            cols.append(s.to_numpy(dtype=float))
        mat = np.column_stack(cols) if cols else np.zeros((len(X), 0))
    else:
        mat = np.asarray(X, dtype=float)
        if mat.ndim == 1:
            mat = mat.reshape(-1, 1)
    mat = np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)
    if not names or len(names) != mat.shape[1]:
        names = [f"f{i}" for i in range(mat.shape[1])]
    return mat.astype(float), [str(n) for n in names]


class Standardizer:
    """Column-wise z-score standardiser fit on training data (no sklearn dependency)."""

    def __init__(self) -> None:
        self.mean_: np.ndarray | None = None
        self.std_: np.ndarray | None = None

    def fit(self, mat: np.ndarray) -> "Standardizer":
        self.mean_ = mat.mean(axis=0)
        std = mat.std(axis=0)
        std[std < 1e-9] = 1.0
        self.std_ = std
        return self

    def transform(self, mat: np.ndarray) -> np.ndarray:
        assert self.mean_ is not None and self.std_ is not None
        return (mat - self.mean_) / self.std_

    def fit_transform(self, mat: np.ndarray) -> np.ndarray:
        return self.fit(mat).transform(mat)
