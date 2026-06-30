"""PU and semi-supervised learning on the unlabeled majority (ML-8; Part 5.4).

Insider fraud has few labels and a vast unlabeled majority. Two complementary tools:
- ``PUClassifier`` — Elkan-Noto: treat unlabeled as negative, then correct probabilities
  by c = P(s=1 | y=1) estimated on held-out labeled positives. Also exposes reliable
  negatives (spy-style) so we never treat 'unknown' as 'benign'.
- ``SelfTrainingClassifier`` — pseudo-label high-confidence unlabeled points and retrain.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier

from ml.config.seeds import GLOBAL_SEED


def _as2d(X) -> np.ndarray:
    return np.asarray(X, dtype=float)


class PUClassifier:
    """Positive-Unlabeled classifier (Elkan & Noto 2008).

    Fit with y in {1 (positive/labeled), 0 (unlabeled)}. Predicts P(y=1 | x) corrected
    by the estimated label frequency c. Reliable negatives are the lowest-scoring unlabeled.
    """

    def __init__(
        self, base=None, val_frac: float = 0.25, seed: int = GLOBAL_SEED
    ) -> None:
        self.base = (
            base
            if base is not None
            else HistGradientBoostingClassifier(random_state=seed)
        )
        self.val_frac = val_frac
        self.seed = seed
        self.c_ = 1.0
        self._clf: Any = None

    def fit(self, X, s) -> "PUClassifier":
        X = _as2d(X)
        s = np.asarray(s).astype(int).ravel()
        rng = np.random.default_rng(self.seed)
        pos = np.flatnonzero(s == 1)
        hold = (
            rng.choice(pos, size=max(1, int(len(pos) * self.val_frac)), replace=False)
            if len(pos)
            else np.array([], int)
        )
        train_mask = np.ones(len(s), bool)
        train_mask[hold] = False
        self._clf = clone(self.base)
        self._clf.fit(X[train_mask], s[train_mask])
        if len(hold):
            self.c_ = float(np.clip(self._raw(X[hold]).mean(), 1e-3, 1.0))
        return self

    def _raw(self, X) -> np.ndarray:
        proba = self._clf.predict_proba(_as2d(X))
        return proba[:, 1] if proba.shape[1] > 1 else proba.ravel()

    def predict_proba_pu(self, X) -> np.ndarray:
        """Elkan-Noto corrected P(y=1|x) = P(s=1|x) / c, clipped to [0,1]."""
        return np.clip(self._raw(X) / self.c_, 0.0, 1.0)

    def reliable_negatives(self, X, quantile: float = 0.2) -> np.ndarray:
        """Indices of the most-confidently-negative rows (lowest corrected score)."""
        scores = self.predict_proba_pu(X)
        thr = np.quantile(scores, quantile)
        return np.flatnonzero(scores <= thr)


class SelfTrainingClassifier:
    """Semi-supervised self-training: pseudo-label confident unlabeled points, retrain."""

    def __init__(
        self,
        base=None,
        threshold: float = 0.9,
        max_iter: int = 3,
        seed: int = GLOBAL_SEED,
    ) -> None:
        self.base = (
            base
            if base is not None
            else HistGradientBoostingClassifier(random_state=seed)
        )
        self.threshold = threshold
        self.max_iter = max_iter
        self.seed = seed
        self._clf: Any = None
        self.n_pseudolabels_ = 0

    def fit(self, X, y) -> "SelfTrainingClassifier":
        """y in {0,1} for labeled, -1 for unlabeled."""
        X = _as2d(X)
        y = np.asarray(y).astype(int).ravel()
        labeled = y != -1
        Xc, yc = X[labeled], y[labeled]
        for _ in range(self.max_iter):
            self._clf = clone(self.base)
            self._clf.fit(Xc, yc)
            unl = ~labeled
            if not unl.any():
                break
            proba = self._clf.predict_proba(X[unl])
            conf = proba.max(axis=1)
            pred = proba.argmax(axis=1)
            take = conf >= self.threshold
            if not take.any():
                break
            unl_idx = np.flatnonzero(unl)[take]
            Xc = np.vstack([Xc, X[unl_idx]])
            yc = np.concatenate([yc, pred[take]])
            labeled[unl_idx] = True
            self.n_pseudolabels_ += int(take.sum())
        return self

    def predict_proba(self, X) -> np.ndarray:
        proba = self._clf.predict_proba(_as2d(X))
        return proba[:, 1] if proba.shape[1] > 1 else proba.ravel()
