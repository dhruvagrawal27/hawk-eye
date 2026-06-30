"""Model governance (ML-23, ML-24; blueprint Part 27 MRM).

* :mod:`model_card`        — auto-generate a per-model model card (intended use, training
  data+hash, features, metrics, limitations, known failure modes, fairness results).
* :mod:`risk_tiering`      — tier a model by impact (scoring > narrative LLM); the tier sets
  validation depth + review cadence.
* :mod:`change_workflow`   — change -> validation -> approval -> deploy state machine that
  GATES deployment (refuses to deploy until every gate is satisfied + independent sign-off).
* :mod:`monitoring`        — ongoing monitoring across drift / decay / stability / outcome
  analysis vs realized fraud, with a retrain recommendation.
* :mod:`validation_report` — (ML-24) model-risk validation report wrapping REAL fairness
  metrics from ``ml.fairness`` with a clearly-labelled SIMULATED independent sign-off.
* ``validation_scope.md``  — the 5 ML-specific independent-validation items.

Governance PROCESS mocks (board policy/committees/DPIA) are PLATFORM's, not here.
Pure-Python (no heavy imports), so everything loads in any process.
"""
from __future__ import annotations

import os

from ml.mlops.governance.change_workflow import (
    ChangeRequest,
    DeploymentGateError,
    GateEvent,
    Stage,
)
from ml.mlops.governance.model_card import ModelCard, generate_model_card
from ml.mlops.governance.monitoring import (
    ModelMonitor,
    MonitoringReport,
    OutcomeAnalysis,
    StabilityReport,
    outcome_analysis,
    score_stability,
)
from ml.mlops.governance.risk_tiering import (
    RiskTierAssessment,
    assess_entry,
    assess_risk_tier,
    tier_policy,
)
from ml.mlops.governance.validation_report import (
    SimulatedSignoff,
    ValidationReport,
    build_validation_report,
    simulate_signoff,
)

VALIDATION_SCOPE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_scope.md")

__all__ = [
    # model card
    "ModelCard",
    "generate_model_card",
    # risk tiering
    "RiskTierAssessment",
    "assess_risk_tier",
    "assess_entry",
    "tier_policy",
    # change workflow
    "Stage",
    "ChangeRequest",
    "GateEvent",
    "DeploymentGateError",
    # monitoring
    "ModelMonitor",
    "MonitoringReport",
    "OutcomeAnalysis",
    "StabilityReport",
    "outcome_analysis",
    "score_stability",
    # validation report (ML-24)
    "SimulatedSignoff",
    "ValidationReport",
    "build_validation_report",
    "simulate_signoff",
    "VALIDATION_SCOPE_PATH",
]
