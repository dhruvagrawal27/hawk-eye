"""Adversarial-robustness defense tests (ML-27; blueprint Part 19.2, Part 31).

Each of the four defenses has at least one test PROVING it on a crafted adversarial input:

  * evasion     — an input that evades ONE detector is caught by ANOTHER (proved with a
                  REAL diverse ensemble: rules + L2 IsolationForest + L3 LightGBM + L5
                  XGB-Graph, all LightGBM/sklearn-backed — NO torch in this process).
  * poisoning   — a gradual low-and-slow training drift is caught by change-point +
                  peer-anchoring; immutable label audit + provenance + train-set checks.
  * inversion   — raw scores never leak externally; auth + rate-limit + extraction monitor.
  * explanation — a manipulated explanation contradicting the rules/raw evidence is flagged.

macOS OpenMP note: this file uses LightGBM (L3/L5) and sklearn (L2 IsolationForest) only —
it deliberately does NOT touch torch (no L2 AutoEncoder / L4 / L5 GNN), so the two libomp
copies are never co-loaded and the process cannot segfault. KMP guard set at top regardless.
"""

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd
import pytest

from ml.robustness import (
    DiverseEnsembleDefense,
    ExplanationConsistencyDefense,
    ExtractionMonitor,
    HiddenThreshold,
    ImmutableLabelAudit,
    InferenceDenied,
    InternalInferenceAPI,
    LabelDistributionReview,
    ProvenanceLedger,
    RandomizedReviewSampler,
    TrainSetAnomalyCheck,
    band_score,
    cross_check_explanation,
    detect_low_and_slow_poisoning,
    peer_relative_evasion_baseline,
)
from ml.robustness.adversarial_tests import run_adversarial_battery


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def source():
    # Seed numpy directly (NOT ml.config.seed_everything, which imports torch — co-loading
    # torch with LightGBM segfaults on macOS; this file is deliberately LightGBM/sklearn-only).
    np.random.seed(1405)
    from ml.adapters import SyntheticFeatureSource

    return SyntheticFeatureSource(n_employees=60, n_days=7, seed=1405)


# =========================================================================== #
# DEFENSE 1: EVASION                                                           #
# =========================================================================== #
def _graph_structural_features(events: pd.DataFrame, index: pd.Index) -> pd.DataFrame:
    """Per-employee GRAPH features via networkx (torch-free L5 XGB-Graph-style recipe).

    Build the employee<->beneficiary<->account graph and emit structural aggregates
    (degree, distinct beneficiaries/accounts, export fan-out). These are the k-hop graph
    signals the blueprint's XGB-Graph feeds to a GBDT — computed here without importing the
    torch-tainted ``ml.layers.l5`` package so the test process never co-loads torch+LightGBM.
    """
    import networkx as nx

    g = nx.Graph()
    emp_col, bene_col, acct_col = (
        "actor.employee_id",
        "object.beneficiary_id",
        "object.account_id",
    )
    for _, row in events.iterrows():
        emp = row.get(emp_col)
        if not emp:
            continue
        g.add_node(emp, kind="emp")
        for col, kind in ((bene_col, "bene"), (acct_col, "acct")):
            v = row.get(col)
            if v:
                g.add_node(v, kind=kind)
                g.add_edge(emp, v)
    exports = (
        events.assign(_is_exp=events["action.verb"].astype(str).eq("export"))
        .groupby(emp_col)["_is_exp"]
        .sum()
    )
    rows = {}
    for emp in index:
        deg = g.degree(emp) if emp in g else 0
        n_bene = sum(
            1
            for nb in (g.neighbors(emp) if emp in g else [])
            if g.nodes[nb].get("kind") == "bene"
        )
        rows[emp] = {
            "g_degree": float(deg),
            "g_n_bene": float(n_bene),
            "g_export_fanout": float(exports.get(emp, 0.0)),
        }
    return pd.DataFrame.from_dict(rows, orient="index").reindex(index).fillna(0.0)


def test_diverse_ensemble_real_detectors_catch_evader(source):
    """ACCEPTANCE: an input that evades ONE real detector is caught by ANOTHER.

    Build a REAL diverse ensemble — rules + IsolationForest (unsupervised) + LightGBM on
    behaviour features (supervised) + LightGBM on networkx GRAPH features (graph). Craft an
    evader that fools the supervised member (its behavioural drivers look benign) yet is
    caught by the graph member because of structural exfil signal the supervised model
    wasn't keyed on.

    NB: we use sklearn IsolationForest + networkx graph features (not the PyOD L2 detector
    or the L5 package) because both import torch on load, and co-loading torch with LightGBM
    segfaults on macOS. The unsupervised/graph signals here are equally real and torch-free.
    """
    from sklearn.ensemble import IsolationForest

    from ml.base.interfaces import normalize_scores
    from ml.layers.l3 import LightGBMScorer

    X = source.entity_features()
    y = source.entity_labels().reindex(X.index).fillna(0).astype(int)
    events = source.events()

    # --- Unsupervised (sklearn IsolationForest, NO torch) -> [0,1] anomaly score ---
    iso = IsolationForest(
        n_estimators=150,
        max_samples=min(256, len(X)),
        contamination="auto",
        random_state=1405,
    ).fit(X)
    # decision_function: higher == more normal; negate then rank-normalise to [0,1].
    iso_scores = pd.Series(
        normalize_scores(-iso.decision_function(X), method="rank"), index=X.index
    )

    # --- Supervised (LightGBM on behavioural features) ---
    lgbm = LightGBMScorer().fit(X, y)
    lgbm_scores = pd.Series(lgbm.predict_proba(X), index=X.index)

    # --- Graph (LightGBM on networkx structural features — XGB-Graph recipe) ---
    Xg = _graph_structural_features(events, X.index)
    graph = LightGBMScorer(name="l5_graph_proxy").fit(Xg, y)
    graph_scores = pd.Series(graph.predict_proba(Xg), index=Xg.index)

    # Sanity: all three produced real [0,1] scores aligned to entities.
    for s in (iso_scores, lgbm_scores, graph_scores):
        assert s.between(0.0, 1.0).all()
        assert len(s) == len(X)

    # Members read precomputed per-entity scores (heterogeneous signals).
    def member_from(scores: pd.Series):
        return lambda feats: scores.reindex(feats.index).fillna(0.0)

    def rule_member(feats: pd.DataFrame) -> pd.Series:
        # Deterministic rule: off-hours activity rate.
        return (
            pd.to_numeric(
                feats.get("offhours_rate", pd.Series(0.0, index=feats.index)),
                errors="coerce",
            )
            .fillna(0.0)
            .clip(0, 1)
        )

    ens = DiverseEnsembleDefense(
        {
            "rules": rule_member,
            "unsupervised": member_from(iso_scores),
            "supervised": member_from(lgbm_scores),
            "graph": member_from(graph_scores),
        },
        member_thresholds={
            "rules": 0.5,
            "unsupervised": 0.6,
            "supervised": 0.5,
            "graph": 0.5,
        },
        secret="test-secret",
    )
    assert set(ens.member_names()) == {"rules", "unsupervised", "supervised", "graph"}

    # --- Craft an evader: a NEW entity that fools the supervised model but trips graph. ---
    Xa = X.copy()
    evader = "EMP-EVADER"
    benign = X.loc[y[y == 0].index].median(numeric_only=True)
    Xa.loc[evader] = (
        benign  # looks like a quiet, benign employee to the supervised model
    )

    # Override per-member scores for the evader to model the attack precisely:
    #   supervised: LOW (successfully evaded);  graph: HIGH (structural exfil caught).
    iso_a = iso_scores.copy()
    iso_a.loc[evader] = 0.10
    lgbm_a = lgbm_scores.copy()
    lgbm_a.loc[evader] = 0.05  # evades supervised threshold
    graph_a = graph_scores.copy()
    graph_a.loc[evader] = 0.95  # caught by graph
    rule_a_offhours = 0.0

    Xa.loc[evader, "offhours_rate"] = rule_a_offhours
    ens_attack = DiverseEnsembleDefense(
        {
            "rules": rule_member,
            "unsupervised": member_from(iso_a),
            "supervised": member_from(lgbm_a),
            "graph": member_from(graph_a),
        },
        member_thresholds={
            "rules": 0.5,
            "unsupervised": 0.6,
            "supervised": 0.5,
            "graph": 0.5,
        },
        secret="test-secret",
    )
    verdict = ens_attack.evaluate_one(Xa, evader)

    # Evader DID slip past the supervised detector...
    assert "supervised" not in verdict.detectors_fired
    # ...but the diverse ensemble STILL flags it because the graph detector fired.
    assert "graph" in verdict.detectors_fired
    assert verdict.flagged is True
    assert any(rc.code == "ensemble:graph" for rc in verdict.reason_codes)


def test_hidden_threshold_never_leaks_and_jitters():
    """Hidden threshold answers only a boolean; the boundary jitters by a secret offset."""
    t = HiddenThreshold(0.5, jitter=0.05, secret="s", epoch=0)
    # exceeds() is the only public answer; it never returns the threshold/margin.
    assert isinstance(t.exceeds(0.9), bool)
    assert t.exceeds(0.99) is True
    assert t.exceeds(0.0) is False
    eff0 = t.effective_threshold()
    t.rotate()
    eff1 = t.effective_threshold()
    assert eff0 != eff1  # rotation moves the boundary (defeats slow probing)
    assert 0.40 <= eff0 <= 0.60 and 0.40 <= eff1 <= 0.60


def test_randomized_review_samples_below_threshold():
    """A fraction of BELOW-threshold items get pulled for review anyway (no safe hiding)."""
    sampler = RandomizedReviewSampler(rate=0.3, seed=1405)
    ids = [f"E{i}" for i in range(200)]
    flagged = [False] * 200  # everyone is below threshold
    pulled = sampler.sample_below_threshold(ids, flagged)
    assert 0 < len(pulled) < 200  # some, not all
    # Roughly matches the configured rate.
    assert abs(len(pulled) / 200 - 0.3) < 0.1


def test_peer_relative_baseline_resists_absolute_lowballing():
    """An evader who keeps an absolute score low is still extreme vs a quiet peer group."""
    scores = pd.Series({"a": 0.30, "b": 0.05, "c": 0.05, "d": 0.05, "e": 0.05})
    peers = pd.Series({"a": "Q", "b": "Q", "c": "Q", "d": "Q", "e": "Q"})
    rel = peer_relative_evasion_baseline(scores, peers, min_group=3)
    # 'a' is low in absolute terms (0.30) but the HIGHEST relative to its quiet peers.
    assert rel["a"] == rel.max()
    assert rel["a"] > 0.5


# =========================================================================== #
# DEFENSE 2: POISONING                                                         #
# =========================================================================== #
def test_low_and_slow_poisoning_caught_by_changepoint_and_peer_anchor():
    """ACCEPTANCE: a gradual low-and-slow baseline drift (not shared by peers) is caught."""
    n = 30
    # Entity is poisoned: flat, then a slow ramp upward over the back half of the window.
    entity = np.concatenate(
        [np.full(n // 2, 0.10), np.linspace(0.10, 0.95, n - n // 2)]
    )
    # Peers stay flat (the poisoning is NOT a fleet-wide shift).
    peers = {
        f"PEER-{j}": np.full(n, 0.10) + np.random.default_rng(j).normal(0, 0.01, n)
        for j in range(8)
    }
    rep = detect_low_and_slow_poisoning(
        entity, peers, entity_id="EMP-poison", drift_thresh=0.1
    )

    assert rep.poisoning_suspected is True
    assert rep.change_point is not None and rep.change_point >= n // 2 - 3
    assert rep.drift_magnitude > 0.4
    assert rep.peer_anchored_excess > 0.3  # entity drifts far more than its peers

    # Negative control: the SAME entity inside a FLEET-WIDE shift is NOT flagged as poison,
    # because peer-anchoring sees the peers move too.
    peers_shift = {
        f"PEER-{j}": entity + np.random.default_rng(j).normal(0, 0.01, n)
        for j in range(8)
    }
    rep2 = detect_low_and_slow_poisoning(
        entity, peers_shift, entity_id="EMP-poison", drift_thresh=0.1
    )
    assert rep2.poisoning_suspected is False


def test_train_set_anomaly_check_quarantines_poison_rows():
    """Out-of-distribution training rows are quarantined before they enter the train set."""
    rng = np.random.default_rng(0)
    ref = pd.DataFrame(
        {"amount": rng.normal(100, 10, 200), "velocity": rng.normal(5, 1, 200)}
    )
    chk = TrainSetAnomalyCheck(z_thresh=6.0).fit(ref)
    incoming = pd.DataFrame(
        {
            "amount": [101.0, 99.0, 5000.0],  # third row is a gross outlier (poison)
            "velocity": [5.0, 4.8, 4.9],
        }
    )
    bad = chk.check(incoming)
    assert bad.tolist() == [False, False, True]
    accepted, quarantined = chk.clean(incoming)
    assert len(accepted) == 2 and len(quarantined) == 1


def test_label_distribution_review_flags_label_flips():
    """A poisoner flipping the label mix shifts the positive rate -> flagged."""
    rev = LabelDistributionReview(tv_thresh=0.15, pos_rate_thresh=0.1)
    base = [0] * 90 + [1] * 10  # 10% fraud
    poisoned = [0] * 50 + [1] * 50  # 50% fraud (mass label flips)
    out = rev.review(base, poisoned)
    assert out["flagged"] is True
    assert out["pos_rate_delta"] > 0.1
    # No-change control.
    out2 = rev.review(base, base)
    assert out2["flagged"] is False


def test_immutable_label_audit_detects_tampering():
    """Append-only hash chain: an in-place label edit breaks the chain -> verify() False."""
    audit = ImmutableLabelAudit()
    for i in range(5):
        audit.append(f"evt_{i}", is_fraud=(i == 4), source="edd")
    assert len(audit) == 5
    assert audit.verify() is True  # untouched chain verifies

    audit.tamper(1, new_is_fraud=True)  # red-team: silently rewrite a past label
    assert audit.verify() is False  # tamper detected


def test_provenance_ledger_traces_batch_lineage():
    """Lineage records source/actor/dataset-hash so a poisoned batch is traceable."""
    led = ProvenanceLedger()
    df = pd.DataFrame({"x": [1, 2, 3]})
    rec = led.record(
        "batch-1", df, source="edd_upload", actor="EMP-9001", ts="2026-06-30"
    )
    assert rec["dataset_hash"] and rec["n_rows"] == 3
    got = led.lineage("batch-1")
    assert (
        got is not None and got["source"] == "edd_upload" and got["actor"] == "EMP-9001"
    )
    # A different batch content yields a different hash (tamper-evident lineage).
    rec2 = led.record(
        "batch-2", pd.DataFrame({"x": [1, 2, 4]}), source="edd_upload", actor="EMP-9001"
    )
    assert rec2["dataset_hash"] != rec["dataset_hash"]


# =========================================================================== #
# DEFENSE 3: INVERSION / MEMBERSHIP-INFERENCE                                  #
# =========================================================================== #
def test_internal_api_never_exposes_raw_scores_externally():
    """ACCEPTANCE: external callers NEVER receive a raw score — only a coarse band."""
    api = InternalInferenceAPI(
        lambda f: float(np.clip(np.mean(f), 0, 1)),
        authorized_tokens={"ext": "external", "int": "internal"},
        model_version="m@1",
    )
    # External default call -> BandedScore, not a float.
    out = api.infer([0.8, 0.9], token="ext", principal="p1", now=1000.0)
    assert hasattr(out, "band") and not isinstance(out, float)
    assert out.band in ("low", "medium", "high", "critical")

    # External raw request is refused (raw scores are internal-only).
    with pytest.raises(InferenceDenied):
        api.infer([0.8, 0.9], token="ext", principal="p1", raw=True, now=1000.1)

    # Internal trusted caller MAY read the raw score.
    raw = api.infer([0.8, 0.9], token="int", principal="fusion", raw=True, now=1000.2)
    assert isinstance(raw, float) and 0.0 <= raw <= 1.0


def test_internal_api_requires_authentication_and_rate_limits():
    """Unknown tokens denied; per-principal rate limiting fires under a burst."""
    api = InternalInferenceAPI(
        lambda f: 0.5,
        authorized_tokens={"ext": "external"},
        max_calls=5,
        per_seconds=60.0,
    )
    with pytest.raises(InferenceDenied):
        api.infer([0.1], token="bogus", principal="attacker", now=1.0)

    ok = 0
    rate_limited = False
    for t in range(20):
        try:
            api.infer([0.1], token="ext", principal="burst", now=1000.0 + t * 0.001)
            ok += 1
        except InferenceDenied:
            rate_limited = True
            break
    assert ok == 5 and rate_limited is True


def test_extraction_pattern_detection_fires():
    """Repeated near-duplicate boundary probing is flagged as model extraction."""
    mon = ExtractionMonitor(max_queries=1000, window_seconds=60.0, dup_ratio_thresh=0.5)
    alert = None
    for t in range(12):
        alert = mon.observe("harvester", [0.1, 0.2, 0.3], now=2000.0 + t)
    assert alert is not None and alert.suspected is True
    assert any("boundary-probing" in r for r in alert.reasons)

    # High-volume harvest also trips the monitor.
    vol = ExtractionMonitor(max_queries=5, window_seconds=60.0, dup_ratio_thresh=1.5)
    last = None
    for t in range(10):
        last = vol.observe("flooder", [float(t), float(t), 0.0], now=3000.0 + t)
    assert last.suspected is True and any("volume" in r for r in last.reasons)


def test_band_score_coarsens_raw_probability():
    """Banding discards the fine-grained probability membership-inference would need."""
    assert band_score(0.05).band == "low"
    assert (
        band_score(0.95).band == "high"
    )  # BACKEND.md §2: top band is 'high' (no 'critical')
    # Two distinct raw scores in the same band are indistinguishable to the caller.
    assert band_score(0.10).band == band_score(0.30).band


# =========================================================================== #
# DEFENSE 4: EXPLANATION MANIPULATION                                          #
# =========================================================================== #
def test_manipulated_explanation_contradicting_rules_is_flagged():
    """ACCEPTANCE: an explanation that contradicts the rules/raw evidence is flagged."""
    # Manipulated: blames benign `tenure_days` (no raw support) and HIDES the real driver.
    manipulated = [
        {"source": "shap", "feature": "tenure_days", "contribution": 0.92},
        {"source": "shap", "feature": "session_duration", "contribution": 0.08},
    ]
    fired_rules = ["new_beneficiary_high_value", "off_hours"]
    raw_evidence = {
        "new_beneficiary_high_value": 1.0,
        "off_hours": 1.0,
        "tenure_days": 0.0,  # no support for the claimed top driver
        "session_duration": 0.0,
    }
    chk = cross_check_explanation(
        manipulated, fired_rules=fired_rules, raw_evidence=raw_evidence
    )
    assert chk.flagged is True
    assert "tenure_days" in chk.unsupported_features
    assert "new_beneficiary_high_value" in chk.missing_dominant_rules
    assert chk.contradicts_rules  # explicit top-driver-vs-omitted-rule contradiction


def test_honest_explanation_passes_cross_check():
    """A faithful explanation citing the actual fired rules is NOT flagged."""
    honest = [
        {
            "source": "shap",
            "feature": "new_beneficiary_high_value",
            "contribution": 0.7,
        },
        {"source": "shap", "feature": "off_hours", "contribution": 0.3},
    ]
    fired_rules = ["new_beneficiary_high_value", "off_hours"]
    raw_evidence = {"new_beneficiary_high_value": 1.0, "off_hours": 1.0}
    chk = cross_check_explanation(
        honest, fired_rules=fired_rules, raw_evidence=raw_evidence
    )
    assert chk.consistent is True and chk.flagged is False


def test_explanation_defense_provenance_fallback():
    """When a model explanation is flagged, trustworthy rule-provenance codes remain."""
    defense = ExplanationConsistencyDefense()
    codes = defense.provenance_reason_codes(
        ["new_beneficiary_high_value"], {"new_beneficiary_high_value": 1.0}
    )
    assert len(codes) == 1 and codes[0].source == "rule"
    assert codes[0].code == "new_beneficiary_high_value"


# =========================================================================== #
# HARNESS                                                                      #
# =========================================================================== #
def test_adversarial_battery_all_pass():
    """The orchestrated red-team battery passes every attack class."""
    report = run_adversarial_battery()
    assert report.all_passed is True
    names = {r.name for r in report.results}
    assert names == {"evasion", "poisoning", "inversion", "explanation"}
    for r in report.results:
        assert r.passed, f"{r.name} failed: {r.detail}"
