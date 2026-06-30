"""Training / retraining / inference pipelines (ML-14..19; blueprint Part 18, 22).

* :mod:`train_dag`  (ML-14) — layer-parameterized training DAG: pull -> features -> train
  -> validate -> calibrate -> register(MLflow) -> optional shadow-deploy. Plain-Python
  ``TrainingDAG`` orchestration + an Airflow factory (SCAFFOLD when airflow absent).
* :mod:`train`      (ML-15) — per-layer training implementations wrapping the layer classes.
* :mod:`feedback`   (ML-16) — EDD active-learning + scheduled retrain + A/B.
* :mod:`repro`      (ML-17) — fixed seeds + dataset/feature hashing + MLflow tracking +
  persisted feature vector / model_version so any score is reconstructable.
* :mod:`inference`  (ML-18) — sync fast lane, async upgrade, cadence, backfill, shadow.
* :mod:`backtest`   (ML-19) — replay historical events -> detection-lift + FP-cost.

Submodules are imported lazily (``__getattr__``) so importing ``ml.pipelines`` does NOT
pull torch + lightgbm into one process at once (the macOS dual-libomp hazard).
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "train_dag",
    "train",
    "feedback",
    "repro",
    "inference",
    "backtest",
    "TrainingDAG",
    "run_training",
]

_LAZY = {
    "train_dag": "ml.pipelines.train_dag",
    "train": "ml.pipelines.train",
    "feedback": "ml.pipelines.feedback",
    "repro": "ml.pipelines.repro",
    "inference": "ml.pipelines.inference",
    "backtest": "ml.pipelines.backtest",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        return importlib.import_module(_LAZY[name])
    if name in ("TrainingDAG", "run_training"):
        mod = importlib.import_module("ml.pipelines.train_dag")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
