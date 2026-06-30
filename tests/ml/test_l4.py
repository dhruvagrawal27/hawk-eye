"""Tests for L4 sequence models (ML-5; blueprint Part 20.4 / 22.2).

Validates the non-negotiable L4 contract:
* SIMPLE BASELINES RUN FIRST (windowed PCA + windowed IsolationForest + matrix-profile
  + a small conv/MLP autoencoder) and produce [0,1] scores over windowed events.
* the deep models (USAD, TranAD, AnomalyTransformer, DeepLog) each train on a TINY
  windowed/sequence dataset with FEW epochs and produce [0,1] scores.
* LAXCAT (supervised) trains and emits attention reason codes that identify WHICH
  VARIABLES and WHICH TIME INTERVALS drove the classification (source="attention").
* the keep-if-beats-baselines gate returns a boolean under a NON-point-adjust metric.
* point-adjust stays disabled (``ml.eval.POINT_ADJUST_ENABLED is False``).

Run: .mlvenv/bin/python -m pytest tests/ml/test_l4.py -q

Kept fast: tiny windows, 1-3 epochs, small models, a subsampled synthetic stream.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import ml.eval
from ml.base import BaseDetector, BaseScorer, ReasonCode
from ml.eval import POINT_ADJUST_ENABLED, average_precision, vus_pr
from ml.layers.l4 import (
    AnomalyTransformer,
    ConvAutoencoderBaseline,
    DeepLog,
    GateResult,
    LAXCAT,
    MatrixProfileDetector,
    TranAD,
    USAD,
    WindowedIsolationForestDetector,
    WindowedPCADetector,
    WindowSet,
    all_baselines,
    build_verb_sequences,
    build_windows,
    keep_if_beats_baselines,
    run_baselines_first,
)
from ml._optional import HAS_TORCH

# torch on macOS can segfault under the default OpenMP thread pool when many tiny
# models train back-to-back; pin to a single thread (also keeps the suite fast).
if HAS_TORCH:  # pragma: no branch
    import torch

    torch.set_num_threads(1)

# Tiny config so the whole module trains in a few seconds.
WINDOW = 8
STRIDE = 4


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
def _aligned_labels(events: pd.DataFrame, src) -> pd.Series:
    """0/1 fraud label per event, indexed identically to ``events`` (RangeIndex)."""
    lab = src.labels().set_index("event_id")["is_fraud"].astype(int)
    y = lab.reindex(events["event_id"]).fillna(0).astype(int)
    y.index = events.index
    return y


@pytest.fixture(scope="module")
def windowed():
    """A small windowed dataset (WindowSet) built from SyntheticFeatureSource events."""
    from ml.adapters import SyntheticFeatureSource

    src = SyntheticFeatureSource(n_employees=40, n_days=6, seed=1405)
    events = src.events()
    y = _aligned_labels(events, src)
    ws = build_windows(events, y, window=WINDOW, stride=STRIDE)
    # sanity: the fixture is non-trivial and separable (has both classes).
    assert len(ws) > 50
    assert 0 < int(ws.y.sum()) < len(ws)
    assert ws.X.shape[1] == WINDOW and ws.X.ndim == 3
    return ws


@pytest.fixture(scope="module")
def verb_seqs():
    """Per-employee integer verb sequences + labels (the DeepLog input)."""
    from ml.adapters import SyntheticFeatureSource

    src = SyntheticFeatureSource(n_employees=40, n_days=6, seed=1405)
    events = src.events()
    y = _aligned_labels(events, src)
    seqs, seq_y, vocab = build_verb_sequences(events, labels=y, by="employee")
    # multi-event sequences are what make the LSTM next-event model meaningful.
    assert max(len(s) for s in seqs) > 5
    assert len(vocab) > 2
    return seqs, np.asarray(seq_y, dtype=int), vocab


def _in_unit_interval(scores: np.ndarray, n: int) -> None:
    scores = np.asarray(scores, dtype=float)
    assert scores.shape == (n,)
    assert np.all(np.isfinite(scores))
    assert float(scores.min()) >= 0.0 - 1e-9
    assert float(scores.max()) <= 1.0 + 1e-9


# --------------------------------------------------------------------------- #
# honest-eval guard                                                            #
# --------------------------------------------------------------------------- #
def test_point_adjust_is_disabled():
    """The single load-bearing honesty invariant for the whole L4 layer."""
    assert POINT_ADJUST_ENABLED is False
    assert ml.eval.POINT_ADJUST_ENABLED is False
    # there is deliberately no point-adjust function to import.
    assert not hasattr(ml.eval, "point_adjust")


# --------------------------------------------------------------------------- #
# windowing                                                                    #
# --------------------------------------------------------------------------- #
def test_build_windows_shapes_and_labels(windowed):
    ws = windowed
    assert isinstance(ws, WindowSet)
    n, w, c = ws.X.shape
    assert w == WINDOW
    assert ws.entity.shape == (n,)
    assert ws.y.shape == (n,)
    assert ws.end_ts.shape == (n,)
    assert len(ws.feature_names) == c
    # the flat view is what PCA / IsolationForest consume.
    assert ws.flat.shape == (n, w * c)
    # labels are 0/1.
    assert set(np.unique(ws.y)).issubset({0, 1})


# --------------------------------------------------------------------------- #
# BASELINES RUN FIRST                                                          #
# --------------------------------------------------------------------------- #
def test_baselines_exist_run_first_and_score_unit_interval(windowed):
    ws = windowed
    scores = run_baselines_first(ws, window=WINDOW)

    # the §20.4 baseline suite is present and ran (before any deep model).
    assert set(scores) == {
        "windowed_pca",
        "windowed_iforest",
        "matrix_profile",
        "conv_ae",
    }
    for name, s in scores.items():
        _in_unit_interval(s, len(ws))

    # the suite is built from real BaseDetector subclasses.
    suite = all_baselines(window=WINDOW)
    assert isinstance(suite["windowed_pca"], WindowedPCADetector)
    assert isinstance(suite["windowed_iforest"], WindowedIsolationForestDetector)
    assert isinstance(suite["matrix_profile"], MatrixProfileDetector)
    assert isinstance(suite["conv_ae"], ConvAutoencoderBaseline)
    for det in suite.values():
        assert isinstance(det, BaseDetector)
        assert det.layer == "L4"


def test_windowed_pca_separates_and_explains(windowed):
    ws = windowed
    det = WindowedPCADetector(n_components=6, window=WINDOW).fit(ws)
    assert det.is_fitted
    s = det.score_samples(ws)
    _in_unit_interval(s, len(ws))
    # PCA reconstruction error should rank fraud windows above benign on this
    # separable synthetic stream.
    assert s[ws.y == 1].mean() > s[ws.y == 0].mean()

    # per-feature reconstruction explanation -> attention reason codes.
    codes = det.explain(ws, top_k=3)
    assert len(codes) == len(ws)
    nonempty = [c for c in codes if c]
    assert nonempty, "PCA baseline should produce per-feature explanations"
    for rc in nonempty[0]:
        assert isinstance(rc, ReasonCode)
        assert rc.source == "attention"
        assert rc.feature in ws.feature_names


def test_isolation_forest_baseline_params(windowed):
    ws = windowed
    det = WindowedIsolationForestDetector(window=WINDOW).fit(ws)
    # blueprint §20.2/§20.4 IsolationForest defaults.
    assert det.n_estimators == 150
    assert det._if.max_features == 1.0
    assert det._if.contamination == "auto"
    _in_unit_interval(det.score_samples(ws), len(ws))


# --------------------------------------------------------------------------- #
# DEEP MODELS — tiny train, [0,1] scores                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAS_TORCH, reason="deep L4 models require torch")
def test_usad_trains_and_scores(windowed):
    ws = windowed
    det = USAD(latent_dim=6, epochs=3).fit(ws)
    assert det.is_fitted and det.layer == "L4"
    assert isinstance(det, BaseDetector)
    _in_unit_interval(det.score_samples(ws), len(ws))


@pytest.mark.skipif(not HAS_TORCH, reason="deep L4 models require torch")
def test_tranad_trains_and_scores(windowed):
    ws = windowed
    det = TranAD(d_model=8, window=WINDOW, epochs=2).fit(ws)
    assert det.is_fitted
    _in_unit_interval(det.score_samples(ws), len(ws))


@pytest.mark.skipif(not HAS_TORCH, reason="deep L4 models require torch")
def test_anomaly_transformer_trains_and_scores(windowed):
    ws = windowed
    det = AnomalyTransformer(d_model=8, window=WINDOW, epochs=2).fit(ws)
    assert det.is_fitted
    _in_unit_interval(det.score_samples(ws), len(ws))


@pytest.mark.skipif(not HAS_TORCH, reason="deep L4 models require torch")
def test_deeplog_torch_next_event(verb_seqs):
    seqs, seq_y, vocab = verb_seqs
    det = DeepLog(hidden=8, window=5, epochs=3, use_torch=True).fit(seqs)
    # multi-event sequences exercise the real LSTM next-event language model.
    assert det._backend_is_torch
    s = det.score_samples(seqs)
    _in_unit_interval(s, len(seqs))
    # next-event surprisal must not collapse to a constant on varied sequences.
    assert len(np.unique(np.round(s, 4))) > 1

    # explanations are attention reason codes about the (surprising) next verb.
    codes = det.explain(seqs)
    assert len(codes) == len(seqs)
    rc = codes[0][0]
    assert rc.source == "attention" and rc.code == "DEEPLOG_NEXT_EVENT"


def test_deeplog_ngram_fallback_is_honest(verb_seqs):
    """DeepLog stays usable (numpy n-gram) even with use_torch=False (or no torch)."""
    seqs, seq_y, vocab = verb_seqs
    det = DeepLog(window=5, epochs=2, use_torch=False).fit(seqs)
    assert not det._backend_is_torch
    assert det._ngram is not None
    s = det.score_samples(seqs)
    _in_unit_interval(s, len(seqs))
    assert len(np.unique(np.round(s, 4))) > 1


# --------------------------------------------------------------------------- #
# LAXCAT — supervised, variable + temporal attention reason codes              #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAS_TORCH, reason="LAXCAT requires torch")
def test_laxcat_supervised_attention_reason_codes(windowed):
    ws = windowed
    clf = LAXCAT(n_intervals=4, conv_channels=4, window=WINDOW, epochs=10).fit(ws, ws.y)
    assert clf.is_fitted
    assert isinstance(clf, BaseScorer) and clf.layer == "L4"

    proba = clf.predict_proba(ws)
    _in_unit_interval(proba, len(ws))

    codes = clf.reason_codes(ws, top_k=3)
    assert len(codes) == len(ws)
    nonempty = [c for c in codes if c]
    assert nonempty, "LAXCAT must emit reason codes for classified windows"

    for rc in nonempty[0]:
        assert isinstance(rc, ReasonCode)
        # source must be attention (BACKEND.md §2 reason source).
        assert rc.source == "attention"
        # WHICH VARIABLE: a real feature name from the window.
        assert rc.feature in ws.feature_names
        # WHICH TIME INTERVAL: the detail names a step range / interval.
        assert rc.detail is not None
        assert "steps[" in rc.detail and "interval" in rc.detail
        # attention weight magnitude.
        assert rc.contribution is not None

    # the dominant interval cited is one of the n_intervals partitions.
    intervals = {rc.detail for row in nonempty for rc in row}
    assert all("/4)" in d for d in intervals)


# --------------------------------------------------------------------------- #
# keep-if-beats-baselines gate (NON point-adjust)                              #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAS_TORCH, reason="gate test trains a deep model")
def test_gate_keeps_deep_when_it_beats_baselines(windowed):
    ws = windowed
    baseline_scores = run_baselines_first(ws, window=WINDOW)
    deep = USAD(latent_dim=6, epochs=3).fit(ws).score_samples(ws)

    res = keep_if_beats_baselines(deep, baseline_scores, ws.y, metric="vus_pr")
    assert isinstance(res, GateResult)
    assert isinstance(res.keep, bool)
    assert res.metric == "vus_pr"
    # the gate's reported metric matches a direct non-PA computation.
    assert res.deep_vus_pr == pytest.approx(vus_pr(ws.y, deep), abs=1e-6)
    # keep iff the deep model's range-aware metric strictly beats the best baseline.
    assert res.keep == (res.deep_vus_pr > res.best_baseline_vus_pr)


def test_gate_rejects_random_deep_model(windowed):
    """A random 'deep' score must NOT beat the real baselines -> keep is False."""
    ws = windowed
    baseline_scores = run_baselines_first(ws, window=WINDOW)
    rng = np.random.default_rng(1405)
    random_deep = rng.random(len(ws))

    res = keep_if_beats_baselines(random_deep, baseline_scores, ws.y, metric="vus_pr")
    assert res.keep is False
    assert res.margin <= 0.0


def test_gate_uses_non_point_adjust_metric_and_supports_ap(windowed):
    ws = windowed
    baseline_scores = run_baselines_first(ws, window=WINDOW)
    pca = baseline_scores["windowed_pca"]

    # average_precision is also a valid (non-PA) gate metric.
    res = keep_if_beats_baselines(
        pca, baseline_scores, ws.y, metric="average_precision"
    )
    assert res.metric == "average_precision"
    assert res.deep_vus_pr == pytest.approx(average_precision(ws.y, pca), abs=1e-6)

    # unknown metrics are rejected (no smuggling in point-adjust).
    with pytest.raises(ValueError):
        keep_if_beats_baselines(pca, baseline_scores, ws.y, metric="point_adjust")
