"""Tests for the fairness workstream (ML-25, ML-26).

No torch / LightGBM here — fairness uses Fairlearn + sklearn + numpy only, which coexist
fine in one process. We synthesize a small dataset with a known sensitive attribute and a
deliberately BIASED scorer so every metric/mitigation has clear signal.
"""

from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import pytest

from ml.config import seed_everything
from ml.fairness import (
    DISPARATE_IMPACT_FLOOR,
    PROTECTED_ATTRIBUTES,
    FairnessMonitor,
    ProtectedFeatureLeak,
    apply_group_thresholds,
    assert_no_protected_features,
    compute_all_fairness_metrics,
    compute_fairness_metric,
    detect_feedback_trap,
    detect_proxies,
    disparate_impact_ratio,
    fairness_alerts,
    fairness_metrics_dict,
    feedback_trap_alerts,
    find_protected_features,
    flagged_proxies,
    group_wise_thresholds,
    normalized_mutual_information,
    peer_relative_mitigation,
    threshold_optimizer,
)


# --------------------------------------------------------------------------- #
# Fixtures: small dataset with a sensitive attribute + a biased scorer         #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def biased_dataset():
    """A dataset where group 'A' is flagged far more often than 'B' for the same risk.

    Includes ALL the protected attributes the blueprint requires, plus a 'branch' that is a
    near-perfect proxy for 'region'.
    """
    seed_everything(1405)
    rng = np.random.default_rng(1405)
    n = 600

    region = rng.choice(["north", "south"], size=n, p=[0.5, 0.5])
    # branch is an (almost) deterministic function of region -> a proxy.
    branch = np.array([f"BR-{r}-{rng.integers(0,2)}" for r in region])

    gender = rng.choice(["f", "m"], size=n)
    department = rng.choice(["trade", "retail", "treasury"], size=n)
    grade = rng.choice(["G1", "G2", "G3"], size=n)
    seniority = rng.choice(["junior", "mid", "senior"], size=n)
    age = rng.integers(22, 60, size=n)
    tenure = rng.integers(100, 4000, size=n)

    # true fraud: same base rate in both regions (so a gap is unfairness, not base rate)
    y_true = (rng.random(n) < 0.15).astype(int)

    # BIASED scorer: north gets a big additive bump, so it's flagged disproportionately.
    base = rng.random(n) * 0.4 + y_true * 0.3
    bias = np.where(region == "north", 0.45, 0.0)
    y_score = np.clip(base + bias, 0, 1)
    y_pred = (y_score >= 0.5).astype(int)

    protected = pd.DataFrame(
        {
            "region": region,
            "branch": branch,
            "gender": gender,
            "department": department,
            "grade": grade,
            "seniority": seniority,
            "age": age,
            "tenure": tenure,
        }
    )
    return dict(
        y_true=y_true,
        y_pred=y_pred,
        y_score=y_score,
        protected=protected,
        region=region,
    )


# --------------------------------------------------------------------------- #
# ML-25 metrics                                                                #
# --------------------------------------------------------------------------- #
def test_disparate_impact_detects_bias(biased_dataset):
    di = disparate_impact_ratio(biased_dataset["y_pred"], biased_dataset["region"])
    assert 0.0 <= di <= 1.0
    # north is flagged much more than south -> DI ratio breaches the 0.8 floor.
    assert di < DISPARATE_IMPACT_FLOOR


def test_single_attribute_metric_all_fields(biased_dataset):
    m = compute_fairness_metric(
        biased_dataset["y_true"],
        biased_dataset["y_pred"],
        biased_dataset["region"],
        attribute="region",
    )
    # all four required metrics computed
    assert m.demographic_parity_difference > 0.1
    assert 0.0 <= m.disparate_impact_ratio < DISPARATE_IMPACT_FLOOR
    assert m.equal_opportunity_difference >= 0.0
    assert m.equalized_odds_difference >= m.equal_opportunity_difference - 1e-9
    assert "disparate_impact" in m.breaches()
    assert m.backend in ("fairlearn", "direct")
    d = m.to_dict()
    assert set(
        [
            "demographic_parity_difference",
            "disparate_impact_ratio",
            "equal_opportunity_difference",
            "equalized_odds_difference",
        ]
    ).issubset(d)


def test_all_protected_attributes_covered(biased_dataset):
    metrics = compute_all_fairness_metrics(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    # every listed protected attribute present in the data is measured
    for attr in PROTECTED_ATTRIBUTES:
        assert attr in metrics, f"missing fairness metric for {attr}"
        m = metrics[attr]
        assert m.disparate_impact_ratio <= 1.0 + 1e-9
        assert m.demographic_parity_difference >= 0.0


def test_continuous_attributes_binned(biased_dataset):
    # age + tenure are continuous; they must still produce >1 group (quantile-binned).
    metrics = compute_all_fairness_metrics(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    assert len(metrics["age"].selection_rates) > 1
    assert len(metrics["tenure"].selection_rates) > 1


def test_metrics_dict_for_ml24(biased_dataset):
    md = fairness_metrics_dict(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    assert md["any_breach"] is True
    assert "region" in md["breaches"]
    assert md["disparate_impact_floor"] == DISPARATE_IMPACT_FLOOR
    assert "attributes" in md and "region" in md["attributes"]


def test_fairness_alerts_carry_reason_codes_and_narrative(biased_dataset):
    metrics = compute_all_fairness_metrics(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    alerts = fairness_alerts(metrics)
    assert alerts, "expected at least one fairness breach alert"
    a = next(al for al in alerts if al["attribute"] == "region")
    assert a["reason_codes"], "alert must carry reason codes"
    rc = a["reason_codes"][0]
    assert rc["source"] == "rule" and rc["code"].startswith("fairness.")
    assert a["narrative"] and isinstance(a["narrative"], str)


def test_no_bias_no_breach():
    seed_everything(7)
    rng = np.random.default_rng(7)
    n = 400
    grp = rng.choice(["x", "y"], size=n)
    y_true = (rng.random(n) < 0.2).astype(int)
    # unbiased scorer: identical distribution regardless of group
    y_pred = (rng.random(n) < 0.2).astype(int)
    m = compute_fairness_metric(y_true, y_pred, grp, attribute="grp")
    assert m.disparate_impact_ratio >= DISPARATE_IMPACT_FLOOR - 0.2  # roughly even
    assert m.demographic_parity_difference < 0.2


# --------------------------------------------------------------------------- #
# ML-25 continuous-monitoring hook                                            #
# --------------------------------------------------------------------------- #
def test_fairness_monitor_hook(biased_dataset):
    mon = FairnessMonitor(attributes=["region", "gender"])
    rec1 = mon.update(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    assert rec1["any_breach"] is True
    assert rec1["batch_index"] == 0
    assert any(a["attribute"] == "region" for a in rec1["alerts"])

    # callable form works as a streaming hook
    rec2 = mon(
        biased_dataset["y_true"], biased_dataset["y_pred"], biased_dataset["protected"]
    )
    assert rec2["batch_index"] == 1
    assert len(mon.history) == 2


def test_monitor_newly_breached_regression():
    seed_everything(3)
    rng = np.random.default_rng(3)
    n = 300
    grp = rng.choice(["a", "b"], size=n)
    y_true = (rng.random(n) < 0.15).astype(int)
    protected = pd.DataFrame({"region": grp})
    mon = FairnessMonitor(attributes=["region"])

    # batch 1: unbiased
    unbiased = (rng.random(n) < 0.2).astype(int)
    mon.update(y_true, unbiased, protected)
    # batch 2: strongly biased toward 'a'
    biased = np.where(
        (grp == "a") & (rng.random(n) < 0.8), 1, (rng.random(n) < 0.05).astype(int)
    )
    mon.update(y_true, biased, protected)
    assert "region" in mon.newly_breached()


# --------------------------------------------------------------------------- #
# ML-26 mitigations                                                           #
# --------------------------------------------------------------------------- #
def test_peer_relative_mitigation_reduces_gap(biased_dataset):
    region = biased_dataset["region"]
    idx = [f"e{i}" for i in range(len(region))]
    scores = pd.Series(biased_dataset["y_score"], index=idx)
    # peer group == region: peer-relative scoring removes the per-region base-rate bump.
    peer = pd.Series(region, index=idx)
    adj = peer_relative_mitigation(scores, peer, min_group=3)
    assert adj.between(0, 1).all()

    before = disparate_impact_ratio((scores >= 0.5).astype(int).to_numpy(), region)
    # threshold the peer-relative scores at their median so selection rate is comparable
    after_pred = (adj >= adj.median()).astype(int).to_numpy()
    after = disparate_impact_ratio(after_pred, region)
    assert after > before  # closer to 1.0 (more even) after peer-relative re-scoring


def test_group_wise_thresholds_equalize_selection(biased_dataset):
    region = biased_dataset["region"]
    score = biased_dataset["y_score"]
    gt = group_wise_thresholds(score, region, objective="selection_rate")
    preds = apply_group_thresholds(score, region, gt)
    di_after = disparate_impact_ratio(preds, region)
    # group-wise thresholds equalise the flagged fraction -> DI ratio near 1.0
    assert di_after > 0.8
    assert set(gt.thresholds) == set(np.unique(region.astype(str)))


def test_threshold_optimizer_postprocessing(biased_dataset):
    res = threshold_optimizer(
        biased_dataset["y_score"],
        biased_dataset["y_true"],
        biased_dataset["region"],
        constraint="demographic_parity",
    )
    # Fairlearn is installed on the reference machine -> available; result is a 0/1 vector.
    assert res.available is True
    assert res.y_pred is not None
    di_after = disparate_impact_ratio(res.y_pred, biased_dataset["region"])
    di_before = disparate_impact_ratio(
        biased_dataset["y_pred"], biased_dataset["region"]
    )
    assert di_after >= di_before  # not worse; typically much more even


def test_assert_no_protected_features_blocks_leak():
    bad = ["amount_z_personal", "offhours_rate", "gender", "branch"]
    with pytest.raises(ProtectedFeatureLeak):
        assert_no_protected_features(bad)
    hits = find_protected_features(bad)
    assert "gender" in hits and "branch" in hits


def test_assert_no_protected_features_passes_clean():
    good = [
        "amount_z_personal",
        "offhours_rate",
        "login_velocity_60m",
        "n_distinct_devices",
    ]
    assert_no_protected_features(good)  # must not raise


def test_assert_allows_vetted_behavioural_feature():
    # a derived behavioural tenure feature can be explicitly allow-listed
    feats = ["tenure_days", "amount_z_peer"]
    assert_no_protected_features(feats, allow=["tenure_days"])


# --------------------------------------------------------------------------- #
# ML-26 proxy detection                                                       #
# --------------------------------------------------------------------------- #
def test_proxy_detection_flags_branch_as_region(biased_dataset):
    protected = biased_dataset["protected"]
    idx = [f"e{i}" for i in range(len(protected))]
    protected = protected.set_axis(idx)
    # candidate features include 'branch' (a proxy for region) and an innocent feature
    features = pd.DataFrame(
        {
            "branch": protected["branch"].to_numpy(),
            "random_feat": np.random.default_rng(0).random(len(idx)),
        },
        index=idx,
    )
    findings = detect_proxies(features, protected[["region"]])
    flagged = flagged_proxies(findings)
    # branch should be flagged as a region proxy
    assert any(
        f.feature == "branch" and f.protected_attribute == "region" for f in flagged
    )
    proxy = next(f for f in flagged if f.feature == "branch")
    assert proxy.value >= proxy.threshold
    assert proxy.reason_codes and proxy.narrative
    # innocent random feature is not flagged as a region proxy
    assert not any(f.feature == "random_feat" and f.is_proxy for f in findings)


def test_normalized_mutual_information_bounds():
    a = pd.Series(["x", "x", "y", "y", "z", "z"])
    assert normalized_mutual_information(a, a) == pytest.approx(1.0, abs=1e-9)
    b = pd.Series(["p", "q", "p", "q", "p", "q"])
    assert 0.0 <= normalized_mutual_information(a, b) <= 1.0


# --------------------------------------------------------------------------- #
# ML-26 feedback-loop trap                                                     #
# --------------------------------------------------------------------------- #
def test_feedback_trap_detects_disproportionate_confirmation():
    seed_everything(11)
    rng = np.random.default_rng(11)
    n = 400
    region = rng.choice(["north", "south"], size=n)
    # disproportionate confirmation: 'north' alerts confirmed 80% of the time, 'south' 20%.
    dispositions = np.where(
        region == "north",
        rng.random(n) < 0.8,
        rng.random(n) < 0.2,
    )
    protected = pd.DataFrame(
        {"region": region, "gender": rng.choice(["f", "m"], size=n)}
    )
    results = detect_feedback_trap(dispositions, protected)
    assert results["region"].disproportionate is True
    assert results["region"].reason_codes and results["region"].narrative
    # suggested correction down-weights the over-confirmed group
    corr = results["region"].suggested_correction
    assert corr and "group_weights" in corr
    north_w = corr["group_weights"]["north"]
    south_w = corr["group_weights"]["south"]
    assert north_w < south_w  # over-confirmed north down-weighted

    alerts = feedback_trap_alerts(results)
    assert any(a["attribute"] == "region" for a in alerts)


def test_feedback_trap_no_flag_when_balanced():
    seed_everything(5)
    rng = np.random.default_rng(5)
    n = 300
    region = rng.choice(["north", "south"], size=n)
    dispositions = rng.random(n) < 0.4  # same confirmation rate regardless of region
    protected = pd.DataFrame({"region": region})
    results = detect_feedback_trap(dispositions, protected)
    assert results["region"].disproportionate is False
    assert feedback_trap_alerts(results) == []


def test_feedback_trap_string_dispositions():
    region = (["north"] * 50) + (["south"] * 50)
    # north mostly confirmed, south mostly cleared
    disp = (["confirmed"] * 45 + ["cleared"] * 5) + (
        ["cleared"] * 45 + ["confirmed"] * 5
    )
    protected = pd.DataFrame({"region": region})
    results = detect_feedback_trap(disp, protected)
    assert results["region"].disproportionate is True
