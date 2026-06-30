"""MLOps + governance (ML-20..24; blueprint Part 18, 22, 27).

* :mod:`registry`             (ML-20) — model registry conventions: every version carries a
  training-data hash, feature schema, metrics, and approving reviewer; champion/challenger
  layout. MLflow when present, else a local JSON registry; artefacts via ``ModelStore``.
* :mod:`inventory`            (ML-20) — MRM model inventory: L2-L6 + LLM gateway with owner,
  purpose, risk tier, data, version, validation status.
* :mod:`promotion`            (ML-21) — champion/challenger + shadow + canary + signature
  verification on load + automatic rollback on metric regression.
* :mod:`drift`                (ML-22) — data drift (PSI/KS) + concept drift (rolling P/R) via
  Evidently with a numpy fallback; a drift-crossing retrain trigger.
* :mod:`threshold_governance` (ML-22) — tune the alert threshold to analyst throughput
  (precision@k, alert-to-true ratio, MTTD, alert budgeting).
* :mod:`governance`           (ML-23, ML-24) — model cards, risk tiering, a deploy-gating
  change workflow, ongoing monitoring, and a validation report (real fairness + simulated
  sign-off) + ``validation_scope.md``.

Submodules import only pandas/numpy/sklearn (+ optional MLflow/Evidently/Fairlearn behind
``ml._optional`` guards) — NO torch or LightGBM — so importing ``ml.mlops`` is safe in any
process (no macOS dual-libomp hazard).
"""
from __future__ import annotations

from ml.mlops.drift import (
    ConceptDriftReport,
    DataDriftReport,
    FeatureDrift,
    RetrainSignal,
    RetrainTrigger,
    data_drift_report,
    ks_statistic,
    population_stability_index,
    rolling_precision_recall,
)
from ml.mlops.inventory import (
    RISK_TIERS,
    VALIDATION_STATUSES,
    InventoryEntry,
    ModelInventory,
    default_inventory,
)
from ml.mlops.promotion import (
    CanaryResult,
    PromotionDecision,
    PromotionManager,
    ShadowResult,
    SignatureError,
    load_verified,
    shadow_evaluate,
    verify_signature,
)
from ml.mlops.registry import (
    STAGE_CHALLENGER,
    STAGE_CHAMPION,
    ModelRecord,
    ModelRegistry,
    model_signature,
)
from ml.mlops.threshold_governance import (
    ThresholdGovernanceResult,
    ThresholdGovernor,
    ThresholdPoint,
)

__all__ = [
    # registry
    "ModelRegistry",
    "ModelRecord",
    "model_signature",
    "STAGE_CHALLENGER",
    "STAGE_CHAMPION",
    # inventory
    "ModelInventory",
    "InventoryEntry",
    "default_inventory",
    "RISK_TIERS",
    "VALIDATION_STATUSES",
    # promotion
    "PromotionManager",
    "PromotionDecision",
    "ShadowResult",
    "CanaryResult",
    "SignatureError",
    "verify_signature",
    "load_verified",
    "shadow_evaluate",
    # drift
    "data_drift_report",
    "DataDriftReport",
    "FeatureDrift",
    "population_stability_index",
    "ks_statistic",
    "rolling_precision_recall",
    "ConceptDriftReport",
    "RetrainTrigger",
    "RetrainSignal",
    # threshold governance
    "ThresholdGovernor",
    "ThresholdGovernanceResult",
    "ThresholdPoint",
]
