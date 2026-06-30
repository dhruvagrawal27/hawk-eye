"""Per-layer training implementations (ML-15; blueprint Part 22.2).

Each ``train_l*`` wraps the existing layer classes with the blueprint's training recipe
and returns a small result dataclass exposing ``.metrics`` and a ``.calibrated`` flag, so
the layer-parameterized :class:`ml.pipelines.train_dag.TrainingDAG` can drive any layer
through the same pull -> features -> train -> validate -> calibrate -> register steps.

IMPORTANT (macOS dual-libomp hazard): the L4/L5 trainers transitively load torch, while
L3/L5/L6 load LightGBM. Co-loading both into one process segfaults. So the per-layer
trainers are imported LAZILY via ``__getattr__`` / :func:`get_trainer` — importing this
package (or one trainer) does NOT pull every layer's heavy deps at once.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

#: layer-name -> (module, attribute) for lazy trainer resolution.
_TRAINER_REFS = {
    "L2": ("ml.pipelines.train.l2", "train_l2"),
    "L3": ("ml.pipelines.train.l3", "train_l3"),
    "L4": ("ml.pipelines.train.l4", "train_l4"),
    "L5": ("ml.pipelines.train.l5", "train_l5"),
    "L6": ("ml.pipelines.train.l6", "train_l6"),
}

LAYERS = tuple(_TRAINER_REFS)

# Names exposed lazily through __getattr__ (module path, attribute).
_LAZY = {
    "train_l2": ("ml.pipelines.train.l2", "train_l2"),
    "train_l3": ("ml.pipelines.train.l3", "train_l3"),
    "train_l4": ("ml.pipelines.train.l4", "train_l4"),
    "train_l5": ("ml.pipelines.train.l5", "train_l5"),
    "train_l6": ("ml.pipelines.train.l6", "train_l6"),
    "L2TrainResult": ("ml.pipelines.train.l2", "L2TrainResult"),
    "L3TrainResult": ("ml.pipelines.train.l3", "L3TrainResult"),
    "L4TrainResult": ("ml.pipelines.train.l4", "L4TrainResult"),
    "L5TrainResult": ("ml.pipelines.train.l5", "L5TrainResult"),
    "L6TrainResult": ("ml.pipelines.train.l6", "L6TrainResult"),
    "LowAndSlowPoisoningGuard": ("ml.pipelines.train.l2", "LowAndSlowPoisoningGuard"),
    "PoisoningGuardResult": ("ml.pipelines.train.l2", "PoisoningGuardResult"),
    "cusum_change_point": ("ml.pipelines.train.l2", "cusum_change_point"),
    "time_decay_weights": ("ml.pipelines.train.l2", "time_decay_weights"),
}


def get_trainer(layer: str) -> Callable:
    """Resolve (lazily import) the trainer callable for a layer, e.g. 'L3' -> train_l3."""
    layer = layer.upper()
    if layer not in _TRAINER_REFS:
        raise ValueError(f"unknown layer {layer!r}; expected one of {LAYERS}")
    mod_name, attr = _TRAINER_REFS[layer]
    return getattr(importlib.import_module(mod_name), attr)


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        mod_name, attr = _LAZY[name]
        return getattr(importlib.import_module(mod_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_trainer",
    "LAYERS",
    "train_l2",
    "train_l3",
    "train_l4",
    "train_l5",
    "train_l6",
    "L2TrainResult",
    "L3TrainResult",
    "L4TrainResult",
    "L5TrainResult",
    "L6TrainResult",
    "LowAndSlowPoisoningGuard",
    "PoisoningGuardResult",
    "cusum_change_point",
    "time_decay_weights",
]
