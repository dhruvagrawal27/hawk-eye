"""Adversarial-robustness defenses (ML-27; blueprint Part 19.2, Part 27, Part 31).

The threat model is an *insider* who knows the controls and adapts. Each defense maps to
a blueprint Part 19.2 mitigation and ships with a test that proves it:

* :mod:`evasion`             — peer-relative baselines (reuse :mod:`ml.design`), hidden
  thresholds, randomized review sampling, and a DIVERSE ENSEMBLE (rules + unsupervised +
  supervised + graph) so an evader of ONE detector is still caught by ANOTHER.
* :mod:`poisoning`           — train-set anomaly checks, change-point + peer-anchored
  baselines, label-distribution review, an immutable label audit (hash chain), and
  provenance/lineage tracking. Catches low-and-slow training-data poisoning.
* :mod:`inversion_defense`   — a rate-limited, authenticated, INTERNAL-ONLY inference
  wrapper that NEVER returns raw scores externally (banded/coarsened output only), plus
  extraction-pattern query monitoring (model-inversion / membership-inference defense).
* :mod:`explanation_defense` — prefer interpretable components + rule provenance, and
  cross-check an explanation against the rules + raw evidence so a manipulated /
  inconsistent explanation is flagged.
* :mod:`adversarial_tests`   — a small harness that orchestrates the above as a red-team
  battery (blueprint Part 31).

Everything here is ALERT-ONLY: defenses raise/flag for a human; they never block.
Every module imports even when optional heavy libs are absent (guarded via
:mod:`ml._optional`); REAL where the lib is present, clean fallback otherwise.
"""
from __future__ import annotations

from ml.robustness.evasion import (
    DiverseEnsembleDefense,
    EnsembleVerdict,
    HiddenThreshold,
    RandomizedReviewSampler,
    peer_relative_evasion_baseline,
)
from ml.robustness.explanation_defense import (
    ExplanationCheck,
    ExplanationConsistencyDefense,
    cross_check_explanation,
)
from ml.robustness.inversion_defense import (
    BandedScore,
    ExtractionMonitor,
    InferenceDenied,
    InternalInferenceAPI,
    band_score,
)
from ml.robustness.poisoning import (
    ImmutableLabelAudit,
    LabelDistributionReview,
    PoisoningReport,
    ProvenanceLedger,
    TrainSetAnomalyCheck,
    detect_low_and_slow_poisoning,
)

__all__ = [
    # evasion
    "DiverseEnsembleDefense",
    "EnsembleVerdict",
    "HiddenThreshold",
    "RandomizedReviewSampler",
    "peer_relative_evasion_baseline",
    # poisoning
    "TrainSetAnomalyCheck",
    "LabelDistributionReview",
    "ImmutableLabelAudit",
    "ProvenanceLedger",
    "PoisoningReport",
    "detect_low_and_slow_poisoning",
    # inversion
    "InternalInferenceAPI",
    "InferenceDenied",
    "ExtractionMonitor",
    "BandedScore",
    "band_score",
    # explanation
    "ExplanationConsistencyDefense",
    "ExplanationCheck",
    "cross_check_explanation",
]
