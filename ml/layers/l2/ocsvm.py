"""One-Class SVM detector (L2; blueprint §20.2 — "smaller-scale").

sklearn ``OneClassSVM`` (RBF). One-Class SVM is O(n^2)-ish, so we subsample the
training set when it is large (default cap 2000 rows) to keep it tractable, per the
"smaller-scale" guidance. Inputs are standardised first (SVMs are scale-sensitive).
``score_samples`` returns rank-normalised anomaly scores in [0,1] (higher = more
anomalous).
"""
from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ml.base import BaseDetector, normalize_scores
from ml.config.seeds import GLOBAL_SEED
from ml.layers.l2._common import Standardizer, as_matrix


class OneClassSVMDetector(BaseDetector):
    """One-Class SVM UEBA detector (sklearn; subsamples large training sets)."""

    layer = "L2"

    def __init__(
        self,
        *,
        kernel: str = "rbf",
        nu: float = 0.05,
        gamma: str | float = "scale",
        max_train: int = 2000,
        random_state: int = GLOBAL_SEED,
        name: str = "l2_ocsvm",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        self.kernel = kernel
        self.nu = nu
        self.gamma = gamma
        self.max_train = max_train
        self.random_state = random_state
        self._scaler = Standardizer()
        self._model: Any = None
        self._feature_names: list[str] = []

    def fit(self, X: Any, y: Optional[Any] = None) -> "OneClassSVMDetector":
        from sklearn.svm import OneClassSVM

        mat, names = as_matrix(X)
        self._feature_names = names
        Z = self._scaler.fit_transform(mat)
        if Z.shape[0] > self.max_train:
            rng = np.random.default_rng(self.random_state)
            sel = rng.choice(Z.shape[0], size=self.max_train, replace=False)
            Z = Z[sel]
        self._model = OneClassSVM(kernel=self.kernel, nu=self.nu, gamma=self.gamma)
        self._model.fit(Z)
        self._fitted = True
        return self

    def _raw_scores(self, X: Any) -> np.ndarray:
        mat, _ = as_matrix(X)
        Z = self._scaler.transform(mat)
        # decision_function: higher => more normal (inside the boundary); negate.
        return -np.asarray(self._model.decision_function(Z), dtype=float)

    def score_samples(self, X: Any) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("OneClassSVMDetector must be fit before scoring")
        return normalize_scores(self._raw_scores(X), method="rank")
