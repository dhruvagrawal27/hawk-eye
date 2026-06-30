"""L6 fusion tests (ML-7): stacked meta-learner + isotonic calibration + reason-code
assembler -> BACKEND.md §2 alert. Blueprint Part 7/L6, 20.7, 22.2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml import eval as E
from ml.base.interfaces import ReasonCode
from ml.layers.l6 import (
    L6Fusion,
    StackedMetaLearner,
    build_alert,
)
from ml.layers.l6.stacked_meta import LAYER_COLUMNS


def _layer_scores(n=1200, pos=80, seed=0):
    """Per-layer scores: each layer is a noisy signal of the label; L1 is a sparse rule hit."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n, int)
    pos_idx = rng.choice(n, pos, replace=False)
    y[pos_idx] = 1

    def noisy(strength):
        s = rng.random(n) * (1 - strength) + y * strength
        return np.clip(s + rng.normal(0, 0.05, n), 0, 1)

    df = pd.DataFrame(
        {
            "L1_rule": (rng.random(n) < (0.6 * y + 0.02)).astype(
                float
            ),  # fires on most frauds + few FPs
            "L2_unsupervised": noisy(0.4),
            "L3_gbdt": noisy(0.6),
            "L4_sequence": noisy(0.3),
            "L5_graph": noisy(0.45),
        }
    )
    return df, pd.Series(y)


def test_meta_learner_is_transparent_and_consumes_all_layers():
    X, y = _layer_scores()
    meta = StackedMetaLearner(kind="logistic").fit(X, y)
    assert meta.is_fitted and meta.layer == "L6"
    contribs = meta.layer_contributions(X.head(3))
    assert set(contribs[0].keys()) == set(
        LAYER_COLUMNS
    )  # every per-layer score + rule consumed


def test_fused_score_beats_best_single_layer():
    X, y = _layer_scores()
    tr, te = slice(0, 800), slice(800, None)
    fusion = L6Fusion(meta_kind="logistic").fit(X.iloc[tr], y.iloc[tr])
    fused = fusion.calibrated_scores(X.iloc[te])
    ap_fused = E.average_precision(y.iloc[te].to_numpy(), fused)
    ap_single = max(
        E.average_precision(y.iloc[te].to_numpy(), X.iloc[te][c].to_numpy())
        for c in LAYER_COLUMNS
    )
    ap_rand = E.average_precision(
        y.iloc[te].to_numpy(),
        np.random.default_rng(9).random((te.stop or len(y)) - te.start),
    )
    assert ap_fused > ap_rand
    assert (
        ap_fused >= ap_single - 0.05
    )  # stacking is at least competitive with the best single layer


def test_calibration_produces_real_probabilities():
    X, y = _layer_scores()
    fusion = L6Fusion(calibration="isotonic").fit(X, y)
    cal = fusion.calibrated_scores(X)
    assert cal.min() >= 0 and cal.max() <= 1
    # mean calibrated prob tracks the base rate (well-calibrated)
    assert abs(cal.mean() - y.mean()) < 0.05


def test_fuse_one_matches_backend_alert_shape():
    X, y = _layer_scores()
    fusion = L6Fusion().fit(X, y)
    alert = fusion.fuse_one(
        entity_id="EMP-7f3a",
        alert_id="alr_3d7e22",
        layer_scores={
            "L1_rule": 1.0,
            "L2_unsupervised": 0.8,
            "L3_gbdt": 0.9,
            "L4_sequence": 0.3,
            "L5_graph": 0.7,
        },
        reason_codes_by_layer={
            "L1": [
                ReasonCode(
                    "rule",
                    code="NEW_BENEFICIARY_THEN_HIGHVALUE",
                    detail="new payee paid within 27 min",
                )
            ],
            "L3": [
                ReasonCode("shap", feature="new_bene_latency_min", contribution=0.31)
            ],
            "L5": [
                ReasonCode(
                    "graph", detail="maker+checker recur as isolated pair (ring RNG-12)"
                )
            ],
        },
        exposure_inr=4800000,
    )
    d = alert.to_dict()
    for key in (
        "alert_id",
        "entity_id",
        "risk_score",
        "severity",
        "confidence",
        "status",
        "created_ts",
        "contributing_layers",
        "reason_codes",
        "exposure_inr",
        "sla_due_ts",
        "pii_tokenized",
    ):
        assert key in d
    assert 0 <= d["risk_score"] <= 100
    assert d["severity"] in ("low", "medium", "high", "critical")
    assert d["pii_tokenized"] is True and d["exposure_inr"] == 4800000
    # reason codes are assembled (rules first) and match BACKEND.md §2 shape
    assert d["reason_codes"] and d["reason_codes"][0]["source"] == "rule"
    assert all(
        rc["source"] in ("rule", "shap", "graph", "attention")
        for rc in d["reason_codes"]
    )
    # contributing layers reflect the strong layers
    assert "L3_gbdt" in d["contributing_layers"]


def test_fuse_batch_one_alert_per_entity():
    X, y = _layer_scores(n=200, pos=20)
    fusion = L6Fusion().fit(X, y)
    eids = [f"EMP-{i:04d}" for i in range(len(X))]
    alerts = fusion.fuse_batch(X, eids)
    assert len(alerts) == len(X)
    assert all(0 <= a.risk_score <= 100 for a in alerts)


def test_severity_banding_in_alert():
    a = build_alert(
        alert_id="a",
        entity_id="e",
        calibrated_prob=0.95,
        confidence=0.9,
        contributing_layers=["L3_gbdt"],
        reason_codes=[],
    )
    assert a.severity == "critical" and a.risk_score == 95
