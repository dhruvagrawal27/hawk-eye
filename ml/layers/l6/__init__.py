"""L6 stacked fusion + calibration + reason-code assembly (ML-7; blueprint Part 7/L6, 20.7)."""
from __future__ import annotations

from ml.layers.l6.calibration import RiskCalibrator, severity_confidence
from ml.layers.l6.fusion import L6Fusion
from ml.layers.l6.reason_codes import assemble_reason_codes, build_alert
from ml.layers.l6.stacked_meta import LAYER_COLUMNS, StackedMetaLearner, assemble_layer_matrix

__all__ = [
    "L6Fusion",
    "StackedMetaLearner",
    "assemble_layer_matrix",
    "LAYER_COLUMNS",
    "RiskCalibrator",
    "severity_confidence",
    "assemble_reason_codes",
    "build_alert",
]
