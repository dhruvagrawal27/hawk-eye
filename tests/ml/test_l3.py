"""Tests for L3 supervised GBDT (ML-4; blueprint Part 20.3).

Validates that LightGBM/XGBoost/CatBoost scorers train with the documented params, score
in [0,1] with fraud > benign, that calibrated probabilities pass a reliability sanity check,
that plain TreeSHAP returns fast reason codes of the right shape, the imbalance utilities
behave, and the benchmark picks a model whose held-out AUPRC beats a random baseline.

Run: .mlvenv/bin/python -m pytest tests/ml/test_l3.py -q
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import pytest

from ml.base import BaseScorer, ReasonCode
from ml.eval import average_precision, temporal_split
from ml.layers.l3 import (
    CalibratedScorer,
    CatBoostScorer,
    LightGBMScorer,
    XGBoostScorer,
    benchmark_scorers,
    class_weight_dict,
    focal_loss_objective,
    negative_subsample,
    reliability_summary,
    scale_pos_weight,
    to_0_100,
)
from ml.layers.l3 import treeshap

SCORER_CLASSES = (LightGBMScorer, XGBoostScorer, CatBoostScorer)

# Keep the suite fast: cap estimators (early stopping ends well before this anyway).
FAST_KW = dict(n_estimators=300)


# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def xy_ts():
    """Real DATA-sim event features + 0/1 labels + a parallel ts column, time-ordered."""
    from ml.adapters import DataSimFeatureSource

    src = DataSimFeatureSource()
    X, y = src.supervised_xy()
    ts = src.events().set_index("event_id")["ts"].reindex(X.index)
    order = pd.to_datetime(ts, utc=True).argsort().to_numpy()
    X = X.iloc[order].reset_index(drop=True)
    y = y.iloc[order].reset_index(drop=True)
    ts = pd.Series(np.asarray(ts)[order]).reset_index(drop=True)
    assert int(y.sum()) >= 5, "need some positives to test on"
    return X, y, ts


def _split(X, y, ts, test_frac=0.25):
    df = X.reset_index(drop=True).copy()
    df["__y"] = np.asarray(y)
    df["__ts"] = np.asarray(ts)
    tr, te = temporal_split(df, "__ts", test_frac=test_frac)
    return (
        tr.drop(columns=["__y", "__ts"]).reset_index(drop=True),
        tr["__y"].to_numpy(),
        te.drop(columns=["__y", "__ts"]).reset_index(drop=True),
        te["__y"].to_numpy(),
    )


# --------------------------------------------------------------------------- #
# imbalance utilities                                                         #
# --------------------------------------------------------------------------- #
def test_scale_pos_weight_and_class_weights(xy_ts):
    X, y, _ = xy_ts
    spw = scale_pos_weight(y)
    neg = int((np.asarray(y) == 0).sum())
    pos = int((np.asarray(y) == 1).sum())
    assert spw == pytest.approx(neg / pos)
    assert spw > 1.0  # fraud is the minority

    cw = class_weight_dict(y)
    assert cw[1] > cw[0] > 0  # positive class up-weighted

    # degenerate inputs do not crash.
    assert scale_pos_weight(np.zeros(10, dtype=int)) == 1.0


def test_negative_subsample_keeps_all_positives_and_ratio(xy_ts):
    X, y, _ = xy_ts
    pos = int(np.asarray(y).sum())
    Xs, ys, kept = negative_subsample(X, y, ratio=5.0, seed=1)
    assert int(np.asarray(ys).sum()) == pos  # all positives kept
    neg_kept = len(ys) - int(np.asarray(ys).sum())
    assert neg_kept <= 5 * pos + 1
    # kept positions are sorted (time order preserved) and index into the original rows.
    assert list(kept) == sorted(kept)
    assert len(Xs) == len(ys) == len(kept)
    with pytest.raises(ValueError):
        negative_subsample(X, y, ratio=0.5)


def test_focal_loss_objective_shapes():
    obj = focal_loss_objective(gamma=2.0, alpha=0.25)
    y = np.array([0, 1, 0, 1, 1])
    raw = np.array([-1.0, 0.5, 2.0, -0.5, 3.0])
    grad, hess = obj(y, raw)
    assert grad.shape == hess.shape == y.shape
    assert np.all(np.isfinite(grad)) and np.all(np.isfinite(hess))
    assert np.all(hess > 0)  # positive-definite hessian for a valid second-order step


# --------------------------------------------------------------------------- #
# the three scorers train, score in [0,1], fraud > benign                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cls", SCORER_CLASSES)
def test_scorer_trains_and_separates(cls, xy_ts):
    X, y, ts = xy_ts
    X_tr, y_tr, X_te, y_te = _split(X, y, ts)

    model = cls(**FAST_KW)
    out = model.fit(X_tr, y_tr)
    assert out is model and model.is_fitted
    assert isinstance(model, BaseScorer)
    assert model.layer == "L3"

    p = model.predict_proba(X_te)
    assert p.shape == (len(X_te),)
    assert float(p.min()) >= 0.0 and float(p.max()) <= 1.0

    # On real data, mean fraud score must exceed mean benign score.
    if y_te.sum() > 0 and (y_te == 0).any():
        assert p[y_te == 1].mean() > p[y_te == 0].mean()

    # AUPRC must beat the random base rate on the held-out (time) split.
    ap = average_precision(y_te, p)
    base = float(y_te.mean())
    assert ap > base, f"{cls.__name__} AP {ap:.3f} did not beat base rate {base:.3f}"


@pytest.mark.parametrize("cls", SCORER_CLASSES)
def test_scorer_documented_param_bands(cls, xy_ts):
    """Constructor must clamp/honour the EXACT blueprint Part 20.3 bands."""
    X, y, _ = xy_ts
    if cls is LightGBMScorer:
        m = cls(num_leaves=1000, learning_rate=0.5, min_child_samples=10, n_estimators=50)
        assert 31 <= m.num_leaves <= 255
        assert 0.02 <= m.learning_rate <= 0.05
        assert 50 <= m.min_child_samples <= 200
        assert 1000 <= m.n_estimators <= 3000
        assert m.max_depth == -1
        assert m.feature_fraction == 0.8 and m.bagging_fraction == 0.8 and m.bagging_freq == 1
        params = m._params(y)
        assert params["objective"] == "binary"
        assert params.get("is_unbalance") is True
    elif cls is XGBoostScorer:
        m = cls(max_depth=20, eta=0.5, min_child_weight=1)
        assert 4 <= m.max_depth <= 8
        assert 0.01 <= m.eta <= 0.05
        assert m.min_child_weight >= 5
        assert m.subsample == 0.8 and m.colsample_bytree == 0.8
        params = m._params(y)
        assert params["tree_method"] == "hist"
        assert params["eval_metric"] == "aucpr"
        assert params["scale_pos_weight"] == pytest.approx(scale_pos_weight(y))
    else:  # CatBoostScorer
        m = cls(depth=20, learning_rate=0.5, l2_leaf_reg=100)
        assert 6 <= m.depth <= 10
        assert 0.03 <= m.learning_rate <= 0.1
        assert 3 <= m.l2_leaf_reg <= 10


# --------------------------------------------------------------------------- #
# TreeSHAP reason codes — fast, right shape, source=shap                        #
# --------------------------------------------------------------------------- #
def test_treeshap_reason_codes_shape_and_speed(xy_ts):
    X, y, ts = xy_ts
    X_tr, y_tr, X_te, _ = _split(X, y, ts)
    model = LightGBMScorer(**FAST_KW).fit(X_tr, y_tr)

    sample = X_te.iloc[:64]
    t0 = time.perf_counter()
    codes = model.reason_codes(sample, top_k=5)
    elapsed = time.perf_counter() - t0

    assert len(codes) == len(sample)
    for row in codes:
        assert 1 <= len(row) <= 5
        for rc in row:
            assert isinstance(rc, ReasonCode)
            assert rc.source == "shap"
            assert rc.feature in X_tr.columns
            assert rc.contribution is not None
        # ranked by |contribution| desc.
        contribs = [abs(rc.contribution) for rc in row]
        assert contribs == sorted(contribs, reverse=True)
    # plain TreeSHAP is fast (blueprint Part 18 budget); generous bound for CI.
    assert elapsed < 5.0


def test_treeshap_direct_helper_and_offline_marker(xy_ts):
    X, y, ts = xy_ts
    X_tr, y_tr, _, _ = _split(X, y, ts)
    model = LightGBMScorer(**FAST_KW).fit(X_tr, y_tr)
    codes = treeshap.tree_shap_reason_codes(model._model, X_tr.iloc[:10], top_k=3)
    assert len(codes) == 10 and all(len(r) <= 3 for r in codes)

    # offline interaction values exist and produce a square per-feature tensor.
    inter = treeshap.offline_interaction_values(model._model, X_tr.iloc[:5])
    nf = X_tr.shape[1]
    assert inter.shape[-1] == inter.shape[-2] == nf


# --------------------------------------------------------------------------- #
# calibration                                                                  #
# --------------------------------------------------------------------------- #
def test_calibrated_scorer_reliability(xy_ts):
    X, y, ts = xy_ts
    X_tr, y_tr, X_te, y_te = _split(X, y, ts)

    cal = CalibratedScorer(LightGBMScorer(**FAST_KW), method="isotonic")
    cal.fit(X_tr, y_tr)
    assert cal.is_fitted

    p = cal.predict_proba(X_te)
    assert float(p.min()) >= 0.0 and float(p.max()) <= 1.0

    rs = reliability_summary(y_te, p)
    base = rs["base_rate"]
    # Mean predicted probability should sit in the ballpark of the base rate (well calibrated).
    assert abs(rs["mean_predicted"] - base) < max(0.05, 3.0 * base)
    assert rs["ece"] < 0.1

    # Still discriminative after calibration.
    assert average_precision(y_te, p) > base

    # reason codes delegate to the base scorer.
    codes = cal.reason_codes(X_te.iloc[:5], top_k=4)
    assert len(codes) == 5 and codes[0][0].source == "shap"


def test_to_0_100():
    assert to_0_100(0.0) == 0
    assert to_0_100(1.0) == 100
    assert to_0_100(0.873) == 87
    assert to_0_100(1.5) == 100 and to_0_100(-0.2) == 0  # clipped


# --------------------------------------------------------------------------- #
# benchmark picks one; chosen model beats random on the held-out split         #
# --------------------------------------------------------------------------- #
def test_benchmark_picks_best_beating_random(xy_ts):
    X, y, ts = xy_ts
    scorers = {
        "l3_lightgbm": LightGBMScorer(**FAST_KW),
        "l3_xgboost": XGBoostScorer(**FAST_KW),
        "l3_catboost": CatBoostScorer(**FAST_KW),
    }
    res = benchmark_scorers(X, y, ts=ts, test_frac=0.25, scorers=scorers)

    assert res.best_name in scorers
    assert len(res.table) == 3
    # table ranked by average_precision descending.
    aps = [r["average_precision"] for r in res.table]
    assert aps == sorted(aps, reverse=True)
    assert res.table[0]["name"] == res.best_name
    for r in res.table:
        assert "predict_latency_ms_per_row" in r

    # The chosen model's held-out AUPRC must beat a random baseline.
    _, _, X_te, y_te = _split(X, y, ts)
    p = res.best_scorer.predict_proba(X_te)
    best_ap = average_precision(y_te, p)
    rng = np.random.default_rng(1405)
    random_ap = average_precision(y_te, rng.random(len(y_te)))
    assert best_ap > random_ap, f"best AP {best_ap:.3f} did not beat random {random_ap:.3f}"
    assert best_ap > float(y_te.mean())


def test_index_order_benchmark_without_ts(xy_ts):
    """benchmark works on an index-order split when no ts column is supplied."""
    X, y, _ = xy_ts
    scorers = {"l3_lightgbm": LightGBMScorer(**FAST_KW)}
    res = benchmark_scorers(X, y, ts=None, test_frac=0.25, scorers=scorers, calibrate=False)
    assert res.best_name == "l3_lightgbm"
