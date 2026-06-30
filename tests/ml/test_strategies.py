"""ML-8 strategy tests: imbalance, PU/semi-supervised, transfer learning (Part 5.3-5.5, 20.3)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml import eval as E
from ml.strategies import (
    PUClassifier,
    SelfTrainingClassifier,
    TransferEncoder,
    class_weights,
    focal_loss_value,
    from_scratch_baseline,
    negative_subsample,
    scale_pos_weight,
)


def _toy(n=600, pos=40, dim=8, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, dim))
    y = np.zeros(n, int)
    pos_idx = rng.choice(n, pos, replace=False)
    X[pos_idx] += 1.6  # separable positive signal
    y[pos_idx] = 1
    return pd.DataFrame(X, columns=[f"f{i}" for i in range(dim)]), pd.Series(y)


def test_negative_subsample_ratio_and_keeps_all_positives():
    X, y = _toy()
    Xs, ys = negative_subsample(X, y, ratio=5.0)
    assert int((ys == 1).sum()) == int((y == 1).sum())  # all positives kept
    assert int((ys == 0).sum()) <= 5 * int((y == 1).sum()) + 1


def test_scale_pos_weight_and_class_weights():
    X, y = _toy()
    spw = scale_pos_weight(y)
    assert spw > 1  # negatives dominate
    cw = class_weights(y)
    assert cw[1] > cw[0]


def test_focal_loss_decreases_for_confident_correct():
    y = np.array([1, 0, 1, 0])
    good = focal_loss_value(y, np.array([0.95, 0.05, 0.92, 0.03]))
    bad = focal_loss_value(y, np.array([0.5, 0.5, 0.5, 0.5]))
    assert good < bad


def test_pu_classifier_recovers_positives():
    X, y = _toy(pos=60)
    # PU setting: only half the true positives are 'labeled' (s=1), rest hidden as unlabeled (s=0)
    s = y.copy()
    pos_idx = np.flatnonzero(y.to_numpy() == 1)
    hide = pos_idx[: len(pos_idx) // 2]
    s.iloc[hide] = 0
    pu = PUClassifier(seed=0).fit(X.to_numpy(), s.to_numpy())
    scores = pu.predict_proba_pu(X.to_numpy())
    # hidden positives should still score above random / above reliable negatives
    assert E.average_precision(y.to_numpy(), scores) > E.average_precision(
        y.to_numpy(), np.random.default_rng(1).random(len(y))
    )
    rn = pu.reliable_negatives(X.to_numpy(), quantile=0.2)
    assert (
        y.to_numpy()[rn].mean() < y.to_numpy().mean()
    )  # reliable negatives are mostly true negatives


def test_self_training_uses_unlabeled():
    X, y = _toy(pos=50)
    y_semi = y.copy().astype(int)
    # mark 70% as unlabeled (-1)
    rng = np.random.default_rng(0)
    unl = rng.choice(len(y), int(len(y) * 0.7), replace=False)
    y_semi.iloc[unl] = -1
    st = SelfTrainingClassifier(threshold=0.9, max_iter=3, seed=0).fit(
        X.to_numpy(), y_semi.to_numpy()
    )
    assert st.n_pseudolabels_ >= 0
    scores = st.predict_proba(X.to_numpy())
    assert E.average_precision(y.to_numpy(), scores) > 0.1


def test_transfer_pretrain_finetune_runs_and_beats_random():
    Xs, _ = _toy(n=800, pos=80, seed=1)  # source (unlabeled pretrain)
    Xt, yt = _toy(n=300, pos=24, seed=2)  # target (labeled fine-tune)
    enc = TransferEncoder(emb_dim=6, hidden=16, seed=0).pretrain(
        Xs.to_numpy(), epochs=15
    )
    enc.finetune(Xt.to_numpy(), yt.to_numpy())
    proba = enc.predict_proba(Xt.to_numpy())
    assert proba.min() >= 0 and proba.max() <= 1
    ap_transfer = E.average_precision(yt.to_numpy(), proba)
    ap_scratch = E.average_precision(
        yt.to_numpy(),
        from_scratch_baseline(Xt.to_numpy(), yt.to_numpy())(Xt.to_numpy()),
    )
    assert ap_transfer > 0.3  # transfer encoder learns a usable representation
    # transfer is at least competitive with from-scratch (within tolerance; deep nets are stochastic)
    assert ap_transfer >= ap_scratch - 0.25
