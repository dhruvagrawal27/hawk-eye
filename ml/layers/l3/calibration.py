"""Probability calibration for L3 scorers (ML-4; blueprint Part 20.3, 22.2).

GBDT margins are NOT probabilities, especially after class-weight/scale_pos_weight/focal
and negative subsampling. The blueprint requires post-hoc calibration (isotonic default,
Platt/sigmoid alternative) on a HELD-OUT set so ``predict_proba`` is a real probability and
the mean predicted probability tracks the base rate.

``CalibratedScorer`` wraps any fitted ``BaseScorer`` (or fits one) and recalibrates its raw
scores. ``to_0_100`` maps a probability to the BACKEND 0-100 risk integer.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml.base import BaseScorer, ReasonCode
from ml.layers.l3 import imbalance


class CalibratedScorer(BaseScorer):
    """Wrap a base ``BaseScorer`` and calibrate its probabilities on a held-out tail.

    method='isotonic' (default, non-parametric, blueprint default) or 'sigmoid' (Platt).
    Calibration is fit on a time-ordered held-out slice (last ``valid_frac`` of fit rows)
    so it never sees the same data twice. Reason codes are delegated to the base scorer.
    """

    layer = "L3"

    def __init__(
        self,
        base: BaseScorer,
        *,
        method: str = "isotonic",
        valid_frac: float = 0.25,
        name: Optional[str] = None,
        version: str = "0.1.0",
    ) -> None:
        if method not in ("isotonic", "sigmoid"):
            raise ValueError("method must be 'isotonic' or 'sigmoid'")
        super().__init__(name=name or f"{base.name}_calibrated", version=version)
        self.base = base
        self.method = method
        self.valid_frac = float(valid_frac)
        self._calibrator = None

    def fit(self, X, y) -> "CalibratedScorer":
        X = X if isinstance(X, pd.DataFrame) else pd.DataFrame(np.asarray(X))
        yarr = imbalance._as_label_array(y)
        n = len(X)
        cut = max(1, int(round(n * (1.0 - self.valid_frac))))
        cut = min(cut, n - 1) if n > 1 else n

        X_fit, y_fit = X.iloc[:cut], yarr[:cut]
        X_cal, y_cal = X.iloc[cut:], yarr[cut:]

        # Fit (or refit) the base model on the training portion only.
        self.base.fit(X_fit, y_fit)

        # If the calibration slice lacks both classes, fall back to calibrating on all rows.
        if X_cal.shape[0] < 2 or y_cal.sum() == 0 or y_cal.sum() == X_cal.shape[0]:
            X_cal, y_cal = X, yarr

        raw = self.base.predict_proba(X_cal)
        self._fit_calibrator(raw, y_cal)
        self._fitted = True
        return self

    def _fit_calibrator(self, raw: np.ndarray, y: np.ndarray) -> None:
        raw = np.clip(np.asarray(raw, dtype=float).ravel(), 0.0, 1.0)
        if self.method == "isotonic":
            from sklearn.isotonic import IsotonicRegression

            cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            cal.fit(raw, y.astype(float))
            self._calibrator = ("isotonic", cal)
        else:  # Platt / sigmoid: logistic regression on the single raw score.
            from sklearn.linear_model import LogisticRegression

            lr = LogisticRegression(max_iter=1000)
            lr.fit(raw.reshape(-1, 1), y.astype(int))
            self._calibrator = ("sigmoid", lr)

    def predict_proba(self, X) -> np.ndarray:
        if not self._fitted or self._calibrator is None:
            raise RuntimeError("CalibratedScorer must be fit before predict_proba")
        raw = np.clip(self.base.predict_proba(X), 0.0, 1.0)
        kind, model = self._calibrator
        if kind == "isotonic":
            p = model.predict(raw)
        else:
            p = model.predict_proba(raw.reshape(-1, 1))[:, 1]
        return np.clip(np.asarray(p, dtype=float).ravel(), 0.0, 1.0)

    def reason_codes(self, X, top_k: int = 5) -> list[list[ReasonCode]]:
        return self.base.reason_codes(X, top_k=top_k)


def to_0_100(p: float) -> int:
    """Map a probability in [0,1] to the BACKEND 0-100 integer risk score."""
    return int(round(float(np.clip(p, 0.0, 1.0)) * 100))


def reliability_summary(y_true, p_pred, n_bins: int = 10) -> dict[str, float]:
    """Quick calibration sanity numbers: base rate, mean predicted, and ECE.

    ``mean_predicted`` should sit in the ballpark of ``base_rate`` for a calibrated model.
    ECE = expected calibration error (lower is better).
    """
    y = imbalance._as_label_array(y_true).astype(float)
    p = np.clip(np.asarray(p_pred, dtype=float).ravel(), 0.0, 1.0)
    base_rate = float(y.mean())
    mean_pred = float(p.mean())
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    idx = np.clip(np.digitize(p, bins[1:-1]), 0, n_bins - 1)
    ece = 0.0
    n = p.size
    for b in range(n_bins):
        mask = idx == b
        if not mask.any():
            continue
        conf = p[mask].mean()
        acc = y[mask].mean()
        ece += (mask.sum() / n) * abs(conf - acc)
    return {"base_rate": base_rate, "mean_predicted": mean_pred, "ece": float(ece)}
