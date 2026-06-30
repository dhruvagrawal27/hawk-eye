"""L6 risk-fusion (BACKEND-12): calibrated 0–100 + severity×confidence + assembled reason codes."""

from fusion.calibration import calibrate_probability, confidence_from, severity_for
from fusion.reason_codes import assemble
from fusion.service import DEFAULT_FUSION, FusionOutput, FusionService
from fusion.treeshap import top_features

__all__ = [
    "FusionService",
    "FusionOutput",
    "DEFAULT_FUSION",
    "calibrate_probability",
    "severity_for",
    "confidence_from",
    "assemble",
    "top_features",
]
