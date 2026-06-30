"""Model-risk validation report (ML-24).

A model-risk-management validation report that wraps **REAL fairness metrics** computed by
:mod:`ml.fairness` (disparate-impact ratio, equalized-odds / equal-opportunity gaps,
demographic-parity differences across the protected attributes) together with a
**clearly-labelled SIMULATED independent-reviewer sign-off**.

# MOCK: the independent-reviewer SIGN-OFF below is SIMULATED, not a real human review.
#       It is deterministically seeded to the model version so the same model always gets
#       the same synthetic reviewer/verdict (reproducible), and every field is explicitly
#       flagged ``simulated=True``. The fairness metrics it wraps are REAL (computed from
#       data via ml.fairness). A real deployment MUST replace the sign-off with an actual
#       independent validation per blueprint Part 27.

The REAL part (fairness metrics) and the MOCK part (sign-off) are kept strictly separate
so a reviewer can never mistake the simulated approval for a genuine one.

HONEST EVAL: fairness metrics are computed on supplied (time-split) data; nothing here
point-adjusts. No heavy model library is imported, so this loads in any process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd

from ml.fairness import fairness_metrics_dict

# Deterministic pool of synthetic reviewer identities (clearly labelled as simulated).
_SIMULATED_REVIEWERS = (
    "sim-reviewer/model-risk-A",
    "sim-reviewer/model-risk-B",
    "sim-reviewer/model-risk-C",
    "sim-reviewer/independent-validation",
)


@dataclass
class SimulatedSignoff:
    """A SIMULATED independent-reviewer sign-off (NOT a real human review).

    Deterministically derived from the model version so it is reproducible. Every instance
    is flagged ``simulated=True`` and labelled in its ``disclaimer``.
    """

    model_version: str
    reviewer: str
    verdict: str  # "approved_with_conditions" | "approved" | "rejected"
    conditions: list[str] = field(default_factory=list)
    simulated: bool = True
    disclaimer: str = (
        "SIMULATED INDEPENDENT-REVIEWER SIGN-OFF — generated deterministically from the model "
        "version for testing/scaffolding. NOT a real human validation. Replace with a genuine "
        "independent sign-off (blueprint Part 27) before production."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "reviewer": self.reviewer,
            "verdict": self.verdict,
            "conditions": list(self.conditions),
            "simulated": self.simulated,
            "disclaimer": self.disclaimer,
        }


def _seed_from_version(model_version: str) -> int:
    return int(hashlib.sha256(model_version.encode()).hexdigest(), 16)


def simulate_signoff(
    model_version: str, *, any_fairness_breach: bool
) -> SimulatedSignoff:
    """Deterministically derive a SIMULATED sign-off seeded to the model version.

    If the REAL fairness metrics show a breach, the simulated verdict downgrades to
    'approved_with_conditions' (or 'rejected' for a severe disparate-impact breach), so the
    mock reacts to the real signal — but it stays clearly labelled as simulated.
    """
    seed = _seed_from_version(model_version)
    reviewer = _SIMULATED_REVIEWERS[seed % len(_SIMULATED_REVIEWERS)]
    if any_fairness_breach:
        verdict = "approved_with_conditions"
        conditions = [
            "Fairness breach detected in REAL metrics — remediate disparate impact / odds gap "
            "before unconditional approval; re-validate on next batch.",
        ]
    else:
        verdict = "approved"
        conditions = []
    return SimulatedSignoff(
        model_version=model_version,
        reviewer=reviewer,
        verdict=verdict,
        conditions=conditions,
    )


@dataclass
class ValidationReport:
    """A model-risk validation report: REAL fairness metrics + a SIMULATED sign-off."""

    model_id: str
    model_version: str
    fairness: dict[str, Any]  # REAL — from ml.fairness
    signoff: SimulatedSignoff  # MOCK — clearly labelled simulated
    conceptual_soundness: str = ""
    data_assessment: str = ""
    performance_summary: dict[str, float] = field(default_factory=dict)

    @property
    def fairness_is_real(self) -> bool:
        # The fairness block comes straight from ml.fairness.fairness_metrics_dict.
        return (
            "attributes" in self.fairness and "disparate_impact_floor" in self.fairness
        )

    @property
    def signoff_is_simulated(self) -> bool:
        return bool(self.signoff.simulated)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "conceptual_soundness": self.conceptual_soundness,
            "data_assessment": self.data_assessment,
            "performance_summary": {
                k: round(float(v), 6) for k, v in self.performance_summary.items()
            },
            "fairness": self.fairness,  # REAL
            "fairness_is_real": self.fairness_is_real,
            "independent_signoff": self.signoff.to_dict(),  # MOCK (labelled simulated)
            "signoff_is_simulated": self.signoff_is_simulated,
        }


def build_validation_report(
    *,
    model_id: str,
    model_version: str,
    y_true: Iterable[Any],
    y_pred: Iterable[Any],
    protected: pd.DataFrame,
    performance_summary: Optional[dict[str, float]] = None,
    conceptual_soundness: str = "",
    data_assessment: str = "",
    gap_threshold: float = 0.1,
) -> ValidationReport:
    """Build a validation report wrapping REAL fairness metrics + a SIMULATED sign-off.

    The fairness section is computed by ``ml.fairness.fairness_metrics_dict`` (real
    disparate-impact / equalized-odds / equal-opportunity / demographic-parity numbers).
    The sign-off is SIMULATED and deterministically seeded to ``model_version``.
    """
    fairness = fairness_metrics_dict(
        y_true, y_pred, protected, gap_threshold=gap_threshold
    )
    signoff = simulate_signoff(
        model_version, any_fairness_breach=bool(fairness.get("any_breach"))
    )
    return ValidationReport(
        model_id=model_id,
        model_version=model_version,
        fairness=fairness,
        signoff=signoff,
        conceptual_soundness=conceptual_soundness
        or "GBDT/ensemble approach is appropriate for imbalanced tabular insider-fraud; "
        "ALERT-ONLY with human disposition. (Auto-generated summary.)",
        data_assessment=data_assessment
        or "Trained/validated on time-split data; synthetic-only limitation noted; "
        "protected attributes excluded from features. (Auto-generated summary.)",
        performance_summary=performance_summary or {},
    )


__all__ = [
    "SimulatedSignoff",
    "simulate_signoff",
    "ValidationReport",
    "build_validation_report",
]
