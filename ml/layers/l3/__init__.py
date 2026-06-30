"""L3 supervised GBDT layer (ML-4; blueprint Part 7/20.3).

LightGBM (default) + XGBoost (robust) + CatBoost (high-card/imbalance), all subclassing
``ml.base.BaseScorer``. Imbalance handled via class weights / scale_pos_weight / focal +
1:3-1:10 negative subsample, then isotonic/Platt calibration so ``predict_proba`` is a real
probability. Live reason codes via plain TreeSHAP (interaction values OFFLINE only).
``benchmark_scorers`` picks the best on a time-based split.

Every heavy library import lives inside methods, so this package always imports even when
lightgbm/xgboost/catboost/shap are absent (clean sklearn fallbacks kick in).
"""

from __future__ import annotations

from ml.layers.l3.calibration import CalibratedScorer, reliability_summary, to_0_100
from ml.layers.l3.catboost_scorer import CatBoostScorer
from ml.layers.l3.imbalance import (
    class_weight_dict,
    focal_loss_objective,
    negative_subsample,
    sample_weight,
    scale_pos_weight,
)
from ml.layers.l3.lightgbm_scorer import LightGBMScorer
from ml.layers.l3.treeshap import (
    offline_interaction_values,
    tree_shap_reason_codes,
)
from ml.layers.l3.xgboost_scorer import XGBoostScorer

__all__ = [
    "LightGBMScorer",
    "XGBoostScorer",
    "CatBoostScorer",
    "CalibratedScorer",
    "to_0_100",
    "reliability_summary",
    "negative_subsample",
    "scale_pos_weight",
    "class_weight_dict",
    "sample_weight",
    "focal_loss_objective",
    "tree_shap_reason_codes",
    "offline_interaction_values",
    "benchmark_scorers",
    "BenchmarkResult",
]


def __getattr__(name):
    # Lazy import of benchmark to avoid importing all scorers' siblings at package load.
    if name in ("benchmark_scorers", "BenchmarkResult"):
        from ml.layers.l3 import benchmark

        return getattr(benchmark, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
