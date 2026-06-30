"""L6 fusion training (ML-15; blueprint Part 22.2, 20.7).

Train the stacked meta-learner over per-layer scores + rule flags, then isotonic
calibrate so the fused output is a real probability (0-100 downstream). Default meta is
logistic (transparent); kind='lightgbm' uses a shallow GBDT.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.eval import average_precision
from ml.layers.l6 import L6Fusion
from ml.layers.l6.stacked_meta import LAYER_COLUMNS, assemble_layer_matrix


@dataclass
class L6TrainResult:
    fusion: L6Fusion
    metrics: dict[str, float]
    n_train: int = 0

    @property
    def calibrated(self) -> bool:
        return True


def train_l6(
    layer_scores: pd.DataFrame,
    y,
    *,
    meta_kind: str = "logistic",
    calibration: str = "isotonic",
) -> L6TrainResult:
    """Fit + calibrate L6 fusion over a per-layer score matrix; report AUPRC."""
    Xdf = layer_scores if isinstance(layer_scores, pd.DataFrame) else assemble_layer_matrix(layer_scores)
    yv = np.asarray(y).astype(int).ravel()

    fusion = L6Fusion(meta_kind=meta_kind, calibration=calibration)
    fusion.fit(Xdf, yv)

    cal = fusion.calibrated_scores(Xdf)
    metrics = {"auprc": average_precision(yv, cal), "mean_calibrated": float(np.mean(cal))}
    return L6TrainResult(fusion=fusion, metrics=metrics, n_train=len(Xdf))


__all__ = ["train_l6", "L6TrainResult", "LAYER_COLUMNS"]
