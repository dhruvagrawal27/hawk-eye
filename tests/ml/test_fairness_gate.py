"""Fairness-gate CI suite (ML-28; blueprint Part 29/31).

The fairness suite GATES the build: a disparate-impact breach must FAIL the gate. We
prove the gate has teeth by feeding it a DELIBERATELY BIASED scorer (it flags one
protected group far more often) and asserting the gate raises/returns failure, while an
even-handed scorer passes.

We use the real ``ml.fairness`` metrics (4/5ths disparate-impact rule + DP/EO/EOdds gaps)
across protected attributes. ALERT-ONLY: the gate raises an alert/build-failure, it never
auto-blocks a person.

Pure pandas/numpy + ml.fairness -> no heavy model, no torch.

Run: .mlvenv/bin/python -m pytest tests/ml/test_fairness_gate.py -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.fairness import (
    DISPARATE_IMPACT_FLOOR,
    compute_all_fairness_metrics,
    fairness_alerts,
    fairness_metrics_dict,
)


# --------------------------------------------------------------------------- #
# the GATE under test: fail the build on any fairness breach                    #
# --------------------------------------------------------------------------- #
class FairnessGateError(AssertionError):
    """Raised when a fairness breach should fail the build."""


def fairness_gate(y_true, y_pred, protected: pd.DataFrame) -> dict:
    """Return the fairness metrics dict; RAISE FairnessGateError on any breach.

    This is the build-gating contract: a disparate-impact (or DP/EO/EOdds) breach must
    stop the build. Mirrors how CI would call ml.fairness before promoting a model.
    """
    report = fairness_metrics_dict(y_true, y_pred, protected)
    if report["any_breach"]:
        raise FairnessGateError(f"fairness gate FAILED: breaches={report['breaches']}")
    return report


@pytest.fixture(scope="module")
def population():
    """A synthetic eval population with a protected attribute + ground-truth labels.

    Large n so per-group selection rates concentrate (the 4/5ths rule is a rate
    statistic — at small n it has spurious variance). One binary protected attribute
    keeps the gate's pass/fail behaviour driven by the SCORER, not sampling noise.
    """
    rng = np.random.default_rng(1405)
    n = 4000
    group = np.where(rng.random(n) < 0.5, "branch_north", "branch_south")
    y_true = (rng.random(n) < 0.1).astype(int)
    protected = pd.DataFrame({"branch": group})
    return rng, n, group, y_true, protected


# --------------------------------------------------------------------------- #
# a BIASED scorer fails the gate                                               #
# --------------------------------------------------------------------------- #
def test_biased_scorer_fails_the_gate(population):
    rng, n, group, y_true, protected = population
    # Biased predictions: 'branch_south' flagged at ~60%, 'branch_north' at ~5%.
    y_pred = np.zeros(n, dtype=int)
    south = group == "branch_south"
    y_pred[south & (rng.random(n) < 0.60)] = 1
    y_pred[~south & (rng.random(n) < 0.05)] = 1

    # The disparate-impact ratio is well below the 0.8 (4/5ths) floor.
    metrics = compute_all_fairness_metrics(y_true, y_pred, protected)
    assert metrics["branch"].disparate_impact_ratio < DISPARATE_IMPACT_FLOOR
    assert metrics["branch"].disparate_impact_breach is True

    # The GATE must fail.
    with pytest.raises(FairnessGateError):
        fairness_gate(y_true, y_pred, protected)

    # And the breach is reported, contestable (reason codes + narrative) per Part 29.2.
    alerts = fairness_alerts(metrics)
    assert alerts, "a breach must raise at least one fairness alert"
    branch_alert = next(a for a in alerts if a["attribute"] == "branch")
    assert "disparate_impact" in branch_alert["breaches"]
    assert branch_alert["reason_codes"], "fairness alert must carry reason codes"
    assert branch_alert[
        "narrative"
    ], "fairness alert must carry a contestable narrative"


# --------------------------------------------------------------------------- #
# an even-handed scorer passes the gate                                       #
# --------------------------------------------------------------------------- #
def test_even_handed_scorer_passes_the_gate(population):
    rng, n, group, y_true, protected = population
    # Group-independent flagging at a uniform ~10% rate.
    y_pred = (rng.random(n) < 0.10).astype(int)

    report = fairness_gate(y_true, y_pred, protected)  # must NOT raise
    assert report["any_breach"] is False
    assert (
        report["attributes"]["branch"]["disparate_impact_ratio"]
        >= DISPARATE_IMPACT_FLOOR
    )


# --------------------------------------------------------------------------- #
# the gate is a real two-sided gate (sanity: it doesn't always pass/fail)       #
# --------------------------------------------------------------------------- #
def test_gate_is_two_sided(population):
    rng, n, group, y_true, protected = population
    biased = np.zeros(n, dtype=int)
    biased[(group == "branch_south") & (rng.random(n) < 0.7)] = 1
    even = (rng.random(n) < 0.10).astype(int)

    failed = False
    try:
        fairness_gate(y_true, biased, protected)
    except FairnessGateError:
        failed = True
    passed = True
    try:
        fairness_gate(y_true, even, protected)
    except FairnessGateError:
        passed = False
    assert failed and passed, "gate must fail biased AND pass even-handed predictions"
