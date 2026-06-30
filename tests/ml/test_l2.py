"""L2 unsupervised detector tests (ML-3).

Behavioural + contract assertions for every L2 detector and the fusion ensemble:
- each detector trains and scores in [0,1] (higher = more anomalous) on the real
  ``DataSimFeatureSource`` per-entity matrix;
- defaults match Part 20.2 EXACTLY (IF 150/256/1.0/'auto'; AE bottleneck/dropout/99pct);
- the AE emits per-feature reconstruction-error reason codes;
- the ensemble fuses 2-3 detectors and its mean anomaly score for FRAUD-ACTOR entities
  exceeds that for BENIGN entities (the headline acceptance check);
- AUPRC beats a random baseline (honest, non-point-adjusted, entity-level eval).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.base import BaseDetector, ReasonCode
from ml.eval import average_precision, precision_at_k
from ml.layers.l2 import (
    AutoEncoderDetector,
    CopodDetector,
    EcodDetector,
    IsolationForestDetector,
    L2Ensemble,
    OneClassSVMDetector,
)
from ml.layers.l2.ensemble import L2Ensemble as _Ens


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def entity_data():
    from ml.adapters import DataSimFeatureSource

    src = DataSimFeatureSource()
    X = src.entity_features()
    y = src.entity_labels().reindex(X.index).fillna(0).astype(int)
    # subsample-safe: keep all fraud actors + a few hundred benign for speed
    assert int(y.sum()) >= 2, "need at least 2 fraud actors for a meaningful test"
    return X, y, src.events()


def _detector_classes():
    return [
        IsolationForestDetector,
        EcodDetector,
        CopodDetector,
        AutoEncoderDetector,
        OneClassSVMDetector,
    ]


# --------------------------------------------------------------------------- #
# contract: every detector trains + scores in [0,1]                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cls", _detector_classes())
def test_detector_trains_and_scores_in_unit_interval(cls, entity_data):
    X, y, _ = entity_data
    det = cls()
    assert isinstance(det, BaseDetector)
    assert det.fit(X) is det
    assert det.is_fitted
    scores = det.score_samples(X)
    assert isinstance(scores, np.ndarray)
    assert scores.shape == (len(X),)
    assert np.all(scores >= 0.0) and np.all(scores <= 1.0)
    assert np.isfinite(scores).all()


def test_scoring_before_fit_raises(entity_data):
    X, _, _ = entity_data
    with pytest.raises(RuntimeError):
        IsolationForestDetector().score_samples(X)


# --------------------------------------------------------------------------- #
# exact Part 20.2 hyperparameters                                              #
# --------------------------------------------------------------------------- #
def test_isoforest_exact_defaults():
    det = IsolationForestDetector()
    assert det.n_estimators == 150
    assert det.max_samples == 256
    assert det.max_features == 1.0
    assert det.expected_rate == "auto"  # contamination='auto'


def test_autoencoder_defaults_match_blueprint():
    ae = AutoEncoderDetector()
    assert 0.25 <= ae.bottleneck_ratio <= 0.5      # bottleneck ~1/4-1/2 input dim
    assert 0.1 <= ae.dropout <= 0.3                # dropout in [0.1, 0.3]
    assert ae.threshold_pct == 99.0               # 99th-pctile flag threshold
    with pytest.raises(ValueError):
        AutoEncoderDetector(dropout=0.5)          # outside [0.1, 0.3] rejected


# --------------------------------------------------------------------------- #
# AutoEncoder per-feature reconstruction explanation                          #
# --------------------------------------------------------------------------- #
def test_autoencoder_emits_per_feature_reason_codes(entity_data):
    X, _, _ = entity_data
    ae = AutoEncoderDetector(epochs=15).fit(X)
    reasons = ae.explain(X, top_k=4)
    assert len(reasons) == len(X)
    # at least one row carries reason codes referencing real feature columns
    nonempty = [r for r in reasons if r]
    assert nonempty, "AE should emit per-feature reconstruction reason codes"
    rc = nonempty[0][0]
    assert isinstance(rc, ReasonCode)
    assert rc.source == "shap"
    assert rc.feature in set(X.columns)
    assert rc.contribution is not None and rc.contribution >= 0.0
    assert len(nonempty[0]) <= 4  # respects top_k

    # 99th-pctile threshold + is_anomaly flag are exposed
    assert ae.threshold_ >= 0.0
    flags = ae.is_anomaly(X)
    assert flags.shape == (len(X),) and flags.dtype == bool


def test_ecod_emits_tail_reason_codes(entity_data):
    X, _, _ = entity_data
    det = EcodDetector().fit(X)
    reasons = det.explain(X, top_k=3)
    assert len(reasons) == len(X)
    nonempty = [r for r in reasons if r]
    assert nonempty
    assert all(rc.feature in set(X.columns) for rc in nonempty[0])


# --------------------------------------------------------------------------- #
# ensemble: fuses 2-3, configurable mean/max, AE-aggregated explain            #
# --------------------------------------------------------------------------- #
def test_ensemble_default_is_three_detectors():
    ens = L2Ensemble()
    assert 2 <= len(ens.detectors) <= 3
    kinds = {type(d).__name__ for d in ens.detectors}
    assert "IsolationForestDetector" in kinds
    assert "EcodDetector" in kinds
    assert "AutoEncoderDetector" in kinds


def test_ensemble_rejects_wrong_detector_count(entity_data):
    with pytest.raises(ValueError):
        L2Ensemble([IsolationForestDetector()])  # only 1 -> invalid


def test_ensemble_max_fusion_runs(entity_data):
    X, _, _ = entity_data
    ens = L2Ensemble(
        [IsolationForestDetector(), EcodDetector()], fuse="max"
    ).fit(X)
    s = ens.score_samples(X)
    assert s.shape == (len(X),)
    assert np.all((s >= 0) & (s <= 1))


def test_ensemble_explain_aggregates_from_autoencoder(entity_data):
    X, _, _ = entity_data
    ens = L2Ensemble(
        [IsolationForestDetector(), AutoEncoderDetector(epochs=12)]
    ).fit(X)
    reasons = ens.explain(X, top_k=3)
    assert len(reasons) == len(X)
    nonempty = [r for r in reasons if r]
    assert nonempty
    assert nonempty[0][0].detail == "autoencoder reconstruction error"


# --------------------------------------------------------------------------- #
# peer-relative baseline hook (§29 fairness / §19.2 evasion)                   #
# --------------------------------------------------------------------------- #
def test_peer_relative_features_zscore():
    X = pd.DataFrame(
        {"amount_mean": [100.0, 110.0, 9000.0, 90.0]},
        index=["a", "b", "c", "d"],
    )
    groups = pd.Series(["pg1", "pg1", "pg1", "pg1"], index=X.index)
    z = _Ens.peer_relative_features(X, groups)
    # the 9000 outlier should have by far the largest positive deviation
    assert z["amount_mean"].idxmax() == "c"
    assert z.loc["c", "amount_mean"] > 1.0
    # global peer group (peer_groups=None) still returns finite z-scores
    z2 = _Ens.peer_relative_features(X, None)
    assert np.isfinite(z2.to_numpy()).all()


def test_peer_groups_from_events(entity_data):
    X, _, events = entity_data
    ens = L2Ensemble()
    pg = ens.peer_groups_from_events(events, X.index)
    # DataSim events carry actor.peer_group; mapping should be derivable + aligned
    if "actor.peer_group" in events.columns:
        assert pg is not None
        assert list(pg.index) == list(X.index)


# --------------------------------------------------------------------------- #
# HEADLINE acceptance: fraud entities score higher; AUPRC beats random         #
# --------------------------------------------------------------------------- #
def test_ensemble_separates_fraud_from_benign(entity_data):
    X, y, _ = entity_data
    ens = L2Ensemble().fit(X)
    scores = ens.score_samples(X)
    yv = y.to_numpy()
    fraud_mean = scores[yv == 1].mean()
    benign_mean = scores[yv == 0].mean()
    assert fraud_mean > benign_mean, (
        f"fraud entities must score higher: fraud={fraud_mean:.3f} benign={benign_mean:.3f}"
    )

    # honest non-PA entity-level eval: AUPRC should beat the random baseline (prevalence)
    ap = average_precision(yv, scores)
    prevalence = float(yv.mean())
    assert ap > prevalence, f"AUPRC {ap:.3f} must beat random prevalence {prevalence:.3f}"
    # and some real fraud should surface in the top-k
    assert precision_at_k(yv, scores, k=max(2, int(yv.sum()))) > 0.0


def test_isoforest_ranks_fraud_above_random(entity_data):
    X, y, _ = entity_data
    det = IsolationForestDetector().fit(X)
    scores = det.score_samples(X)
    yv = y.to_numpy()
    assert average_precision(yv, scores) > float(yv.mean())
