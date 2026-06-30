"""L2 unsupervised UEBA detectors (ML-3; blueprint §7, §20.2).

Per-entity behavioural anomaly detection: Isolation Forest (primary), parameter-free
ECOD/COPOD, an MLP/PCA autoencoder with per-feature reconstruction explanations, and
One-Class SVM. ``L2Ensemble`` fits 2-3 and fuses normalised scores, with a
peer-relative baseline hook (fairness + evasion resistance, §19.2/§29).

Library of choice is **PyOD**; every detector degrades to a numpy/sklearn fallback so
the module always imports. Defaults match Part 20.2 EXACTLY.
"""
from __future__ import annotations

from ml.layers.l2.autoencoder import AutoEncoderDetector
from ml.layers.l2.ecod_copod import CopodDetector, EcodDetector
from ml.layers.l2.ensemble import L2Ensemble
from ml.layers.l2.isoforest import IsolationForestDetector
from ml.layers.l2.ocsvm import OneClassSVMDetector

__all__ = [
    "IsolationForestDetector",
    "EcodDetector",
    "CopodDetector",
    "AutoEncoderDetector",
    "OneClassSVMDetector",
    "L2Ensemble",
]
