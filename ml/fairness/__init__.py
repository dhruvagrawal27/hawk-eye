"""Fairness metrics + mitigations (ML-25, ML-26; blueprint Part 29).

* ``metrics``        — disparate-impact + DP/EO/EOdds gaps across grade/seniority, age,
  gender, region/branch, department, tenure; a continuous-monitoring hook
  (:class:`FairnessMonitor`); and a metrics dict feeding ML-24.
* ``mitigations``    — peer-group-relative scoring (reuses ``ml.design.peer_relative_scores``);
  pre/in/post-processing mitigations (group-wise thresholds, Fairlearn ThresholdOptimizer);
  and ``assert_no_protected_features`` (protected attrs NEVER used as features).
* ``proxy_detection``— detect proxies for protected attributes (branch as a region/caste proxy)
  via mutual-information / correlation.
* ``feedback_trap``  — monitor EDD confirmation distributions for disproportionate group
  confirmation (the feedback-loop fairness trap) and suggest a correction.

Every alert path carries reason codes + a narrative (``ml.narrative``) so findings are
explainable/contestable (Part 29.2). ALERT-ONLY: nothing here auto-blocks a person.
"""
from __future__ import annotations

from ml.fairness.feedback_trap import (
    DEFAULT_CONFIRMATION_RATIO_FLOOR,
    FeedbackTrapResult,
    GroupConfirmation,
    analyze_attribute,
    detect_feedback_trap,
    feedback_trap_alerts,
    suggest_correction,
)
from ml.fairness.metrics import (
    DEFAULT_GAP_THRESHOLD,
    DISPARATE_IMPACT_FLOOR,
    PROTECTED_ATTRIBUTES,
    FairnessMetric,
    FairnessMonitor,
    compute_all_fairness_metrics,
    compute_fairness_metric,
    disparate_impact_ratio,
    fairness_alerts,
    fairness_metrics_dict,
    group_tpr_fpr,
    selection_rates,
)
from ml.fairness.mitigations import (
    GroupThresholds,
    ProtectedFeatureLeak,
    ThresholdOptimizerResult,
    apply_group_thresholds,
    assert_no_protected_features,
    find_protected_features,
    group_wise_thresholds,
    peer_relative_mitigation,
    threshold_optimizer,
)
from ml.fairness.proxy_detection import (
    DEFAULT_PROXY_THRESHOLD,
    ProxyFinding,
    abs_correlation,
    detect_proxies,
    flagged_proxies,
    normalized_mutual_information,
)

__all__ = [
    # metrics
    "PROTECTED_ATTRIBUTES",
    "DISPARATE_IMPACT_FLOOR",
    "DEFAULT_GAP_THRESHOLD",
    "FairnessMetric",
    "FairnessMonitor",
    "compute_fairness_metric",
    "compute_all_fairness_metrics",
    "disparate_impact_ratio",
    "selection_rates",
    "group_tpr_fpr",
    "fairness_metrics_dict",
    "fairness_alerts",
    # mitigations
    "peer_relative_mitigation",
    "group_wise_thresholds",
    "apply_group_thresholds",
    "GroupThresholds",
    "threshold_optimizer",
    "ThresholdOptimizerResult",
    "assert_no_protected_features",
    "find_protected_features",
    "ProtectedFeatureLeak",
    # proxy detection
    "DEFAULT_PROXY_THRESHOLD",
    "ProxyFinding",
    "detect_proxies",
    "flagged_proxies",
    "normalized_mutual_information",
    "abs_correlation",
    # feedback trap
    "DEFAULT_CONFIRMATION_RATIO_FLOOR",
    "FeedbackTrapResult",
    "GroupConfirmation",
    "analyze_attribute",
    "detect_feedback_trap",
    "feedback_trap_alerts",
    "suggest_correction",
]
