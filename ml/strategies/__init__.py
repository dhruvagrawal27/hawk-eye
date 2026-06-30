"""Shared learning strategies (ML-8): imbalance, PU/semi-supervised, transfer learning."""

from __future__ import annotations

from ml.strategies.imbalance import (
    class_weights,
    focal_loss_lgb,
    focal_loss_value,
    negative_subsample,
    scale_pos_weight,
)
from ml.strategies.pu_semisupervised import PUClassifier, SelfTrainingClassifier
from ml.strategies.transfer_learning import (
    TransferEncoder,
    from_scratch_baseline,
    load_public_source,
)

__all__ = [
    "negative_subsample",
    "scale_pos_weight",
    "class_weights",
    "focal_loss_lgb",
    "focal_loss_value",
    "PUClassifier",
    "SelfTrainingClassifier",
    "TransferEncoder",
    "from_scratch_baseline",
    "load_public_source",
]
