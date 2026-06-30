"""Tests for MLOps + governance (ML-20..24).

REAL assertions against the acceptance criteria:
* every registered model carries data-hash / features / metrics / approving reviewer;
* the inventory lists all L2-L6 + the LLM gateway, each with a risk tier;
* a challenger promotes ONLY after beating the champion in shadow + signature verify, and a
  simulated metric regression triggers auto-rollback; a bad signature is rejected on load;
* PSI/KS + rolling precision/recall are computed and a threshold crossing fires a retrain;
* the alert threshold tunes to a daily capacity budget;
* a model card auto-generates with ALL sections and the change workflow GATES deploy;
* the validation report contains REAL disparate-impact/equalized-odds metrics + a clearly
  labelled SIMULATED sign-off.

ENV: this file uses only numpy/pandas/sklearn (NO torch, NO LightGBM), so there is no macOS
dual-libomp hazard. We set KMP_DUPLICATE_LIB_OK defensively anyway.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from ml.mlops import (
    InventoryEntry,
    ModelInventory,
    ModelRegistry,
    PromotionManager,
    RetrainTrigger,
    ShadowResult,
    SignatureError,
    ThresholdGovernor,
    data_drift_report,
    default_inventory,
    ks_statistic,
    population_stability_index,
    rolling_precision_recall,
    shadow_evaluate,
    verify_signature,
)
from ml.mlops.governance import (
    ChangeRequest,
    DeploymentGateError,
    ModelMonitor,
    Stage,
    assess_risk_tier,
    build_validation_report,
    generate_model_card,
    simulate_signoff,
)
from ml.mlops.promotion import load_verified
from ml.mlops.registry import STAGE_CHALLENGER, STAGE_CHAMPION

# --------------------------------------------------------------------------- #
# fixtures                                                                     #
# --------------------------------------------------------------------------- #
FEATURES = ["amount_z", "off_hours", "new_bene", "velocity"]


def _make_xy(n=400, seed=0, signal=1.0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(n, len(FEATURES))), columns=FEATURES)
    logit = signal * (X["amount_z"] + 0.8 * X["off_hours"] + 0.6 * X["new_bene"])
    p = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.random(n) < p).astype(int)
    # guarantee both classes present
    y[:5] = 1
    y[5:10] = 0
    return X, pd.Series(y, name="is_fraud")


def _fit(X, y, C=1.0):
    return LogisticRegression(max_iter=500, C=C).fit(X, y)


class _NoiseModel:
    """A model fit on an irrelevant noise column -> cannot separate fraud (weak baseline).

    Its ``predict_proba`` ignores the live X and returns noise-driven probabilities of the
    right length, so it reliably loses an AUPRC shadow comparison to a real model.
    """

    def __init__(self, y_train, *, n_train, n_shadow):
        noise_tr = pd.DataFrame(
            {"noise": np.random.default_rng(0).normal(size=n_train)}
        )
        self._m = LogisticRegression(max_iter=500).fit(noise_tr, y_train)
        self._shadow = pd.DataFrame(
            {"noise": np.random.default_rng(1).normal(size=n_shadow)}
        )

    def predict_proba(self, _X):
        return self._m.predict_proba(self._shadow)[:, 1]


@pytest.fixture
def registry(tmp_path):
    return ModelRegistry(root=str(tmp_path / "registry"), use_mlflow=False)


# --------------------------------------------------------------------------- #
# ML-20: registry lineage                                                     #
# --------------------------------------------------------------------------- #
def test_registered_model_carries_full_lineage(registry):
    rec = registry.register(
        name="l3_supervised",
        version="1.0.0",
        layer="L3",
        training_data_hash="deadbeef",
        feature_names=FEATURES,
        metrics={"auprc": 0.71, "recall_at_k": 0.5},
        approving_reviewer="alice@bank",
        stage=STAGE_CHALLENGER,
    )
    assert rec.training_data_hash == "deadbeef"
    assert rec.feature_names == FEATURES
    assert rec.metrics["auprc"] == 0.71
    assert rec.approving_reviewer == "alice@bank"
    assert rec.signature  # signature computed
    assert rec.is_complete  # data-hash + features + metrics + reviewer all present

    # persisted + queryable
    got = registry.get("l3_supervised", "1.0.0")
    assert got is not None and got.is_complete


def test_incomplete_registration_rejected(registry):
    with pytest.raises(ValueError):
        registry.register(
            name="l3_supervised",
            version="0.0.1",
            layer="L3",
            training_data_hash=None,  # missing
            feature_names=FEATURES,
            metrics={},  # missing
            approving_reviewer=None,  # missing
        )


def test_champion_challenger_layout(registry):
    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h1",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    registry.register(
        name="m",
        version="1.1.0",
        layer="L3",
        training_data_hash="h2",
        feature_names=FEATURES,
        metrics={"auprc": 0.65},
        approving_reviewer="r",
        stage=STAGE_CHALLENGER,
    )
    assert registry.champion("m").version == "1.0.0"
    assert [c.version for c in registry.challengers("m")] == ["1.1.0"]

    registry.promote("m", "1.1.0", reviewer="approver")
    assert registry.champion("m").version == "1.1.0"
    # old champion archived, no longer a challenger
    assert "1.1.0" not in [c.version for c in registry.challengers("m")]


# --------------------------------------------------------------------------- #
# ML-20: inventory                                                            #
# --------------------------------------------------------------------------- #
def test_inventory_lists_all_layers_with_risk_tier():
    inv = default_inventory()
    assert inv.covers_all_layers()  # L2-L6 + LLM
    layers = inv.layers_covered
    for required in ("L2", "L3", "L4", "L5", "L6", "LLM"):
        assert required in layers
    for e in inv.entries():
        assert e.risk_tier  # every model has a risk tier
    # scoring (L6 fusion) outranks the narrative LLM
    by_id = {e.model_id: e for e in inv.entries()}
    assert by_id["l6_fusion"].risk_tier == "tier-1-critical"
    assert by_id["llm_narrative_gateway"].decides is False


def test_inventory_reconcile_flags_version_drift(registry):
    registry.register(
        name="l3",
        version="2.0.0",
        layer="L3",
        training_data_hash="h",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    inv = ModelInventory(
        [
            InventoryEntry(
                model_id="l3_supervised",
                layer="L3",
                owner="o",
                purpose="p",
                risk_tier="tier-1-critical",
                data="d",
                version="1.0.0",
            )
        ],
        defaults=False,
    )
    mismatches = inv.reconcile(registry)
    assert any(
        m["layer"] == "L3" and m["registry_champion_version"] == "2.0.0"
        for m in mismatches
    )


# --------------------------------------------------------------------------- #
# ML-21: signature verification, shadow gating, auto-rollback                  #
# --------------------------------------------------------------------------- #
def test_signature_verify_and_reject_on_load(registry):
    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
    )
    rec = registry.get("m", "1.0.0")
    assert verify_signature(rec, FEATURES)
    # correct schema loads
    assert load_verified(registry, "m", "1.0.0", FEATURES) is not None
    # tampered/drifted feature schema is rejected
    assert not verify_signature(rec, FEATURES + ["sneaky_leak"])
    with pytest.raises(SignatureError):
        load_verified(registry, "m", "1.0.0", FEATURES[:-1])


def test_challenger_promotes_only_after_beating_champion_in_shadow(registry):
    X, y = _make_xy(seed=1)
    Xtr, ytr = X.iloc[:300], y.iloc[:300]
    Xsh, ysh = X.iloc[300:], y.iloc[300:]  # time-split shadow slice

    challenger = _fit(Xtr, ytr, C=1.0)  # uses informative features -> strong
    champion = _NoiseModel(
        ytr, n_train=len(Xtr), n_shadow=len(Xsh)
    )  # noise-only -> weak

    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h0",
        feature_names=FEATURES,
        metrics={"auprc": 0.5},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    registry.register(
        name="m",
        version="2.0.0",
        layer="L3",
        training_data_hash="h1",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHALLENGER,
    )

    mgr = PromotionManager(registry)
    dec = mgr.evaluate_and_promote(
        "m", "2.0.0", challenger, champion, Xsh, ysh, FEATURES, reviewer="approver"
    )
    assert dec.signature_ok
    assert dec.shadow.beats_champion
    assert dec.promoted
    assert registry.champion("m").version == "2.0.0"


def test_weaker_challenger_does_not_promote(registry):
    X, y = _make_xy(seed=2)
    Xtr, ytr = X.iloc[:300], y.iloc[:300]
    Xsh, ysh = X.iloc[300:], y.iloc[300:]
    champion = _fit(Xtr, ytr, C=1.0)  # informative features -> strong
    challenger = _NoiseModel(
        ytr, n_train=len(Xtr), n_shadow=len(Xsh)
    )  # noise-only -> weaker

    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    registry.register(
        name="m",
        version="2.0.0",
        layer="L3",
        training_data_hash="h2",
        feature_names=FEATURES,
        metrics={"auprc": 0.5},
        approving_reviewer="r",
        stage=STAGE_CHALLENGER,
    )
    mgr = PromotionManager(registry)
    dec = mgr.evaluate_and_promote(
        "m", "2.0.0", challenger, champion, Xsh, ysh, FEATURES
    )
    assert not dec.shadow.beats_champion
    assert not dec.promoted
    assert registry.champion("m").version == "1.0.0"  # champion unchanged


def test_bad_signature_blocks_promotion(registry):
    X, y = _make_xy(seed=3)
    champ = _fit(X, y)
    chal = _fit(X, y, C=2.0)
    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    registry.register(
        name="m",
        version="2.0.0",
        layer="L3",
        training_data_hash="h2",
        feature_names=FEATURES,
        metrics={"auprc": 0.6},
        approving_reviewer="r",
        stage=STAGE_CHALLENGER,
    )
    mgr = PromotionManager(registry)
    # live feature schema does NOT match registered signature -> reject, never promote
    dec = mgr.evaluate_and_promote("m", "2.0.0", chal, champ, X, y, FEATURES + ["leak"])
    assert not dec.signature_ok
    assert not dec.promoted


def test_metric_regression_triggers_auto_rollback(registry):
    X, y = _make_xy(seed=4)
    good = _fit(X, y, C=1.0)

    class _BadModel:
        """A regressed 'new champion' that scores ~randomly (simulated regression)."""

        def predict_proba(self, Xin):
            rng = np.random.default_rng(99)
            return rng.random(len(Xin))

    registry.register(
        name="m",
        version="1.0.0",
        layer="L3",
        training_data_hash="h",
        feature_names=FEATURES,
        metrics={"auprc": 0.7},
        approving_reviewer="r",
        stage=STAGE_CHAMPION,
    )
    registry.register(
        name="m",
        version="2.0.0",
        layer="L3",
        training_data_hash="h2",
        feature_names=FEATURES,
        metrics={"auprc": 0.7},
        approving_reviewer="r",
    )
    registry.promote("m", "2.0.0", reviewer="r")  # new champion deployed
    assert registry.champion("m").version == "2.0.0"

    mgr = PromotionManager(registry)
    canary = mgr.canary("m", _BadModel(), good, X, y, prior_version="1.0.0")
    assert canary.rolled_back
    assert canary.rolled_back_to == "1.0.0"
    assert registry.champion("m").version == "1.0.0"  # auto-rolled back


# --------------------------------------------------------------------------- #
# ML-22: drift PSI/KS + concept drift + retrain trigger                        #
# --------------------------------------------------------------------------- #
def test_psi_and_ks_detect_shift():
    rng = np.random.default_rng(0)
    ref = rng.normal(0, 1, 1000)
    same = rng.normal(0, 1, 1000)
    shifted = rng.normal(3, 1, 1000)

    assert population_stability_index(ref, same) < 0.1  # stable
    assert population_stability_index(ref, shifted) > 0.25  # significant shift

    _, p_same = ks_statistic(ref, same)
    stat_shift, p_shift = ks_statistic(ref, shifted)
    assert p_same > 0.05
    assert p_shift < 0.05 and stat_shift > 0.3


def test_data_drift_report_and_retrain_trigger():
    rng = np.random.default_rng(1)
    ref = pd.DataFrame(rng.normal(0, 1, (500, len(FEATURES))), columns=FEATURES)
    cur = ref.copy()
    cur["amount_z"] = rng.normal(4, 1, 500)
    cur["velocity"] = rng.normal(4, 1, 500)  # 2 of 4 features drift (>= 0.3 share)

    report = data_drift_report(ref, cur)
    assert report.any_drift
    assert report.n_drifted >= 2
    assert report.backend in ("numpy", "evidently")

    trig = RetrainTrigger(drift_share_threshold=0.3)
    signal = trig.evaluate(data_drift=report)
    assert signal.triggered
    assert signal.reasons


def test_no_drift_no_retrain():
    rng = np.random.default_rng(2)
    ref = pd.DataFrame(rng.normal(0, 1, (500, len(FEATURES))), columns=FEATURES)
    cur = pd.DataFrame(rng.normal(0, 1, (500, len(FEATURES))), columns=FEATURES)
    report = data_drift_report(ref, cur)
    signal = RetrainTrigger().evaluate(data_drift=report)
    assert not signal.triggered


def test_concept_drift_rolling_precision_recall_triggers_retrain():
    # First 100 dispositions: model is right (precision high). Last 100: model degrades.
    good_true = [1, 0] * 50
    good_pred = [1, 0] * 50  # perfect
    bad_true = [1, 0] * 50
    bad_pred = [0, 1] * 50  # inverted -> precision collapses
    y_true = good_true + bad_true
    y_pred = good_pred + bad_pred

    cdr = rolling_precision_recall(y_true, y_pred, window=100, step=100)
    assert cdr.precision_drop > 0.1
    assert cdr.degraded

    signal = RetrainTrigger(metric_drop_threshold=0.1).evaluate(concept_drift=cdr)
    assert signal.triggered


# --------------------------------------------------------------------------- #
# ML-22: threshold governance to a daily budget                               #
# --------------------------------------------------------------------------- #
def test_threshold_tunes_to_daily_budget():
    rng = np.random.default_rng(5)
    n = 1000
    y = (rng.random(n) < 0.1).astype(int)
    # scores correlated with y so higher threshold => higher precision
    scores = np.clip(0.2 + 0.6 * y + rng.normal(0, 0.2, n), 0, 1)

    gov = ThresholdGovernor(daily_budget=30, horizon_days=1.0, k=20)
    result = gov.tune(y, scores)
    # the chosen operating point fits the budget
    assert result.chosen.expected_daily_alerts <= 30
    assert result.chosen.within_budget
    # operational metrics present
    assert 0.0 <= result.chosen.precision <= 1.0
    assert result.chosen.mean_time_to_disposition_hours > 0
    assert result.chosen.precision_at_k >= 0.0
    assert np.isfinite(
        result.chosen.alert_to_true_ratio
    ) or result.chosen.alert_to_true_ratio == float("inf")

    # a tiny budget forces a more conservative (>=) threshold than a generous budget
    tight = ThresholdGovernor(daily_budget=5, horizon_days=1.0).tune(y, scores)
    loose = ThresholdGovernor(daily_budget=500, horizon_days=1.0).tune(y, scores)
    assert tight.chosen.expected_daily_alerts <= loose.chosen.expected_daily_alerts


# --------------------------------------------------------------------------- #
# ML-23: model card auto-generation (all sections)                            #
# --------------------------------------------------------------------------- #
def test_model_card_has_all_sections(registry):
    X, y = _make_xy(seed=6)
    rec = registry.register(
        name="l3_supervised",
        version="1.0.0",
        layer="L3",
        training_data_hash="abc123",
        feature_names=FEATURES,
        metrics={"auprc": 0.72, "recall_at_k": 0.55},
        approving_reviewer="val@bank",
    )
    entry = default_inventory().get("l3_supervised")
    # real fairness metrics for the card
    protected = pd.DataFrame(
        {"department": np.where(np.arange(len(y)) % 2 == 0, "A", "B")}
    )
    from ml.fairness import fairness_metrics_dict

    fairness = fairness_metrics_dict(y, (X["amount_z"] > 0).astype(int), protected)
    card = generate_model_card(rec, entry, fairness=fairness)

    assert card.is_complete
    assert not card.missing_sections()
    assert card.intended_use and card.training_data_hash == "abc123"
    assert card.features == FEATURES
    assert card.metrics["auprc"] == 0.72
    assert card.limitations and card.known_failure_modes
    assert "attributes" in card.fairness  # real fairness section wired in
    md = card.to_markdown()
    for section in (
        "Intended use",
        "Training data",
        "Features",
        "Metrics",
        "Limitations",
        "Known failure modes",
        "Fairness results",
    ):
        assert section in md


def test_risk_tiering_scoring_outranks_narrative():
    fusion = assess_risk_tier(
        model_id="l6", layer="L6", decides=True, blocks_or_final=True
    )
    llm = assess_risk_tier(model_id="llm", layer="LLM", decides=False)
    assert fusion.risk_tier == "tier-1-critical"
    assert llm.risk_tier == "tier-3-moderate"
    # higher tier => stricter policy
    assert fusion.policy["requires_independent_signoff"]
    assert fusion.policy["review_frequency"] == "monthly"


# --------------------------------------------------------------------------- #
# ML-23: change -> validation -> approval -> deploy GATE                       #
# --------------------------------------------------------------------------- #
def test_change_workflow_gates_deploy():
    cr = ChangeRequest(
        change_id="C1",
        model_id="l3",
        model_version="2.0.0",
        author="dev@bank",
        risk_tier="tier-1-critical",
    )
    # cannot deploy straight away
    assert not cr.can_deploy()
    with pytest.raises(DeploymentGateError):
        cr.deploy()

    # validation must pass + card complete + shadow passed
    cr.validate(passed=True, model_card_complete=True, shadow_passed=True)
    assert cr.stage == Stage.VALIDATED

    # author cannot self-approve (separation of duties)
    with pytest.raises(DeploymentGateError):
        cr.approve(approver="dev@bank")

    cr.approve(approver="independent@bank")
    assert cr.stage == Stage.APPROVED
    assert cr.can_deploy()
    cr.deploy()
    assert cr.stage == Stage.DEPLOYED


def test_change_workflow_blocks_without_shadow():
    cr = ChangeRequest(
        change_id="C2",
        model_id="l3",
        model_version="2.0.0",
        author="dev",
        risk_tier="tier-1-critical",
        requires_shadow=True,
    )
    cr.validate(passed=True, model_card_complete=True, shadow_passed=False)
    assert cr.stage == Stage.REJECTED  # shadow missing -> not validated
    assert "shadow" in " ".join(cr.deployment_blockers()).lower()
    assert not cr.can_deploy()


# --------------------------------------------------------------------------- #
# ML-23: ongoing monitoring                                                   #
# --------------------------------------------------------------------------- #
def test_monitoring_consolidates_and_recommends_retrain():
    rng = np.random.default_rng(7)
    ref = pd.DataFrame(rng.normal(0, 1, (300, len(FEATURES))), columns=FEATURES)
    cur = ref.copy()
    cur["amount_z"] = rng.normal(5, 1, 300)
    cur["velocity"] = rng.normal(5, 1, 300)

    y_true = [1, 0] * 50 + [1, 0] * 50
    y_pred = [1, 0] * 50 + [0, 1] * 50  # degrades

    realized = (rng.random(300) < 0.1).astype(int)
    risk = np.clip(0.2 + 0.6 * realized + rng.normal(0, 0.2, 300), 0, 1)

    mon = ModelMonitor("l3_supervised")
    report = mon.run(
        reference_features=ref,
        current_features=cur,
        disposition_y_true=y_true,
        disposition_y_pred=y_pred,
        reference_scores=risk[:150],
        current_scores=risk[150:],
        realized_fraud=realized,
        risk_scores=risk,
        rolling_window=100,
        alert_threshold=0.5,
    )
    assert report.data_drift is not None
    assert report.concept_drift is not None
    assert report.stability is not None
    assert report.outcome is not None
    assert report.retrain_recommended  # drift + decay both present
    assert report.retrain_reasons
    assert not report.healthy


# --------------------------------------------------------------------------- #
# ML-24: validation report (REAL fairness + SIMULATED sign-off)               #
# --------------------------------------------------------------------------- #
def test_validation_report_real_fairness_and_simulated_signoff():
    X, y = _make_xy(seed=8)
    y_pred = (X["amount_z"] > 0).astype(int)
    protected = pd.DataFrame(
        {
            "department": np.where(np.arange(len(y)) % 2 == 0, "trade", "retail"),
            "gender": np.where(np.arange(len(y)) % 3 == 0, "F", "M"),
        }
    )
    report = build_validation_report(
        model_id="l3_supervised",
        model_version="l3_supervised@1.0.0",
        y_true=y,
        y_pred=y_pred,
        protected=protected,
        performance_summary={"auprc": 0.7},
    )
    d = report.to_dict()
    # REAL fairness: disparate-impact + equalized-odds metrics present per attribute
    assert report.fairness_is_real
    assert "attributes" in d["fairness"]
    for attr in ("department", "gender"):
        m = d["fairness"]["attributes"][attr]
        assert "disparate_impact_ratio" in m
        assert "equalized_odds_difference" in m
        assert "equal_opportunity_difference" in m

    # SIMULATED sign-off: clearly labelled, deterministic to the version
    assert report.signoff_is_simulated
    assert d["independent_signoff"]["simulated"] is True
    assert "SIMULATED" in d["independent_signoff"]["disclaimer"].upper()
    assert d["independent_signoff"]["verdict"] in (
        "approved",
        "approved_with_conditions",
        "rejected",
    )

    # deterministic seeding: same version -> same reviewer
    s1 = simulate_signoff("l3_supervised@1.0.0", any_fairness_breach=False)
    s2 = simulate_signoff("l3_supervised@1.0.0", any_fairness_breach=False)
    assert s1.reviewer == s2.reviewer


def test_shadow_evaluate_metric_contract():
    X, y = _make_xy(seed=9)
    Xtr, ytr = X.iloc[:300], y.iloc[:300]
    Xte, yte = X.iloc[300:], y.iloc[300:]
    strong = _fit(Xtr, ytr, C=1.0)  # uses the informative features
    # weak champion: fits only an irrelevant noise column, so it can't separate fraud
    noise = pd.DataFrame({"noise": np.random.default_rng(0).normal(size=len(Xtr))})
    noise_te = pd.DataFrame({"noise": np.random.default_rng(1).normal(size=len(Xte))})

    class _NoiseChampion:
        def __init__(self, model):
            self._m = model

        def predict_proba(self, _Xin):
            return self._m.predict_proba(noise_te)[:, 1]

    weak = _NoiseChampion(LogisticRegression(max_iter=500).fit(noise, ytr))
    res = shadow_evaluate(weak, strong, Xte, yte)
    assert isinstance(res, ShadowResult)
    assert res.beats_champion  # strong challenger beats noise-only champion
    assert res.margin > 0
    assert res.n == len(yte)
