"""Behavioral CI suite (ML-28; blueprint Part 31).

Known fraud must score HIGH and known-benign LOW on the synthetic red-team library
(the 12 DATA-sim typologies). We run REAL fitted detectors/scorers:

  * L2 ensemble (IsolationForest + ECOD, NO torch AE -> safe alongside the
    LightGBM-backed L3 scorer in the SAME process) over per-entity UEBA features, and
  * the L3 supervised scorer over per-event features,

and assert that fraud entities/events RANK ABOVE benign ones (mean rank + AUPRC beats a
random baseline). This is the headline acceptance check of Part 31.

LightGBM and torch must NOT co-load in one process on macOS (dual libomp segfault); this
file deliberately uses ONLY tree/sklearn/PyOD detectors -> no torch import anywhere.

Run: .mlvenv/bin/python -m pytest tests/ml/test_behavioral.py -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.adapters import DataSimFeatureSource
from ml.eval import average_precision
from ml.layers.l2 import EcodDetector, IsolationForestDetector, L2Ensemble
from ml.layers.l3 import LightGBMScorer


# --------------------------------------------------------------------------- #
# fixtures (session-scoped: the DATA sim run loads once)                       #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def src():
    return DataSimFeatureSource()


@pytest.fixture(scope="module")
def entity_data(src):
    X = src.entity_features()
    y = src.entity_labels().reindex(X.index).fillna(0).astype(int)
    assert int(y.sum()) >= 2, "need fraud actors in the red-team library"
    assert int((y == 0).sum()) >= 10, "need a benign majority"
    return X, y


@pytest.fixture(scope="module")
def event_data(src):
    X, y = src.supervised_xy()
    ts = src.events().set_index("event_id")["ts"].reindex(X.index)
    order = pd.to_datetime(ts, utc=True).argsort().to_numpy()
    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    assert int(y.sum()) >= 5, "need fraud events"
    return X, y


def _mean_rank(scores: np.ndarray, mask: np.ndarray) -> float:
    """Average percentile-rank (0..1, higher = scored more anomalous) of masked rows."""
    order = scores.argsort().argsort().astype(float)
    pct = order / max(len(scores) - 1, 1)
    return float(pct[mask].mean())


# --------------------------------------------------------------------------- #
# L2 unsupervised: fraud ENTITIES rank above benign on the red-team library    #
# --------------------------------------------------------------------------- #
def test_l2_ensemble_fraud_entities_rank_above_benign(entity_data):
    X, y = entity_data
    yv = y.to_numpy()
    # Ensemble WITHOUT the torch AutoEncoder member -> no libomp conflict in-process.
    ens = L2Ensemble(detectors=[IsolationForestDetector(), EcodDetector()])
    ens.fit(X)
    scores = np.asarray(ens.score_samples(X), dtype=float)
    assert scores.shape == (len(X),)
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)

    fraud_mean = scores[yv == 1].mean()
    benign_mean = scores[yv == 0].mean()
    assert (
        fraud_mean > benign_mean
    ), f"fraud entities must score higher (fraud={fraud_mean:.3f} benign={benign_mean:.3f})"
    # Rank-based: fraud actors sit in the upper half on average.
    assert _mean_rank(scores, yv == 1) > _mean_rank(scores, yv == 0)


def test_l2_ensemble_beats_random_auprc(entity_data):
    X, y = entity_data
    yv = y.to_numpy()
    ens = L2Ensemble(detectors=[IsolationForestDetector(), EcodDetector()])
    ens.fit(X)
    scores = np.asarray(ens.score_samples(X), dtype=float)
    ap = average_precision(yv, scores)
    base = float(yv.mean())  # prevalence == expected AP of a random ranker
    assert ap > base, f"L2 AUPRC {ap:.3f} must beat random baseline {base:.3f}"


# --------------------------------------------------------------------------- #
# L3 supervised: fraud EVENTS rank above benign                                #
# --------------------------------------------------------------------------- #
def test_l3_scorer_fraud_events_rank_above_benign(event_data):
    X, y = event_data
    yv = y.to_numpy()
    scorer = LightGBMScorer(n_estimators=300)
    scorer.fit(X, y)
    p = scorer.predict_proba(X)
    assert p.shape == (len(X),)
    assert np.all(p >= 0.0) and np.all(p <= 1.0)

    assert (
        p[yv == 1].mean() > p[yv == 0].mean()
    ), "fraud events must score higher than benign"
    # The worked-example burst (4.8M off-hours new-beneficiary approval) must rank high.
    assert _mean_rank(p, yv == 1) > 0.5


def test_l3_known_fraud_high_known_benign_low_at_threshold(event_data):
    """At an operating threshold, recall on known fraud beats the benign false-positive rate."""
    X, y = event_data
    yv = y.to_numpy()
    scorer = LightGBMScorer(n_estimators=300)
    scorer.fit(X, y)
    p = scorer.predict_proba(X)
    thr = float(np.quantile(p, 0.90))  # top-decile alert budget
    recall_fraud = float((p[yv == 1] >= thr).mean())
    fpr_benign = float((p[yv == 0] >= thr).mean())
    assert (
        recall_fraud > fpr_benign
    ), f"known fraud recall@thr {recall_fraud:.2f} must exceed benign FPR {fpr_benign:.2f}"
