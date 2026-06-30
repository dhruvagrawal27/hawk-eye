"""L6 calibration to a 0-100 risk score with severity × confidence (ML-7; Part 20.7, 22.2).

Isotonic calibration maps the meta-learner probability to a real fraud probability, so the
0-100 score is operationally meaningful (the alert threshold is set against analyst capacity).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from ml.base.interfaces import Severity, severity_from_score


class RiskCalibrator:
    """Calibrate meta probabilities and emit 0-100 score + severity + confidence."""

    def __init__(self, method: str = "isotonic") -> None:
        if method not in ("isotonic", "sigmoid"):
            raise ValueError("method must be 'isotonic' or 'sigmoid'")
        self.method = method
        self._cal = None

    def fit(self, proba: np.ndarray, y: np.ndarray) -> "RiskCalibrator":
        p = np.asarray(proba, dtype=float).ravel()
        yv = np.asarray(y).astype(int).ravel()
        if self.method == "isotonic":
            self._cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, yv)
        else:
            self._cal = LogisticRegression(max_iter=1000).fit(p.reshape(-1, 1), yv)
        return self

    def calibrate(self, proba: np.ndarray) -> np.ndarray:
        p = np.asarray(proba, dtype=float).ravel()
        if self._cal is None:
            return p
        if self.method == "isotonic":
            return np.clip(self._cal.predict(p), 0.0, 1.0)
        return self._cal.predict_proba(p.reshape(-1, 1))[:, 1]

    def to_risk_0_100(self, proba: np.ndarray) -> np.ndarray:
        return np.rint(self.calibrate(proba) * 100).astype(int)


def severity_confidence(calibrated_p: float) -> tuple[Severity, float]:
    """Map a calibrated probability to (severity, confidence).

    Severity from the 0-100 band; confidence = distance from the decision boundary (0.5),
    so a probability near 0 or 1 is high-confidence and one near 0.5 is low-confidence.
    """
    risk = calibrated_p * 100
    sev = severity_from_score(risk)
    confidence = float(min(1.0, abs(calibrated_p - 0.5) * 2))
    return sev, confidence
