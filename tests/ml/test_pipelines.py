"""Tests for the training / retraining / inference pipelines (ML-14..19).

ACCEPTANCE (blueprint Part 18/22):
* the layer-parameterized DAG runs end-to-end for a layer param and registers a
  CALIBRATED artifact (test_dag_*),
* the L2 low-and-slow poisoning guard resists a gradual-shift attack (test_poisoning_*),
* L4 keeps a deep model only if it beats baselines (test_l4_gate_*),
* feedback active-learning surfaces uncertain/high-value cases and a retrain consumes new
  labels (test_feedback_*),
* a score is reconstructable from persisted feature-vector + model_version (test_repro_*),
* sync scores L2/L3 and async L4/L5 UPGRADE (never block) (test_sync_*, test_async_*),
* shadow emits no alerts (test_shadow_*),
* backtest yields detection-lift + FP-cost (test_backtest_*).

macOS dual-libomp note: this whole file is TORCH-FREE. Every layer exercised here uses
LightGBM / sklearn (L2 IsolationForest+ECOD ensemble, L3/L5/L6 GBDT, L4 PCA/IForest/
matrix-profile baselines). We never construct a torch-based model (AE / USAD / GraphSAGE)
in this process, so LightGBM and torch are never co-loaded. KMP guard set defensively.

Run: .mlvenv/bin/python -m pytest tests/ml/test_pipelines.py -q
"""

from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import tempfile

import numpy as np
import pandas as pd
import pytest

from ml.adapters import (
    DataSimFeatureSource,
    Disposition,
    LabelStore,
    SyntheticFeatureSource,
    featurize,
)
from ml.layers.l2 import EcodDetector, IsolationForestDetector, L2Ensemble
from ml.layers.l3 import LightGBMScorer
from ml.pipelines import backtest as bt_mod
from ml.pipelines import feedback, repro
from ml.pipelines.inference import (
    CADENCES,
    SYNC_LATENCY_BUDGET_MS,
    AsyncUpgrader,
    ClickHouseSource,
    ShadowScorer,
    SyncFastLane,
    backfill_rescore,
    is_async_layer,
    is_sync_layer,
)
from ml.pipelines.train.l2 import LowAndSlowPoisoningGuard, cusum_change_point, train_l2
from ml.pipelines.train.l4 import _align_labels_to_events
from ml.pipelines.train_dag import TrainingDAG, make_airflow_dag, run_training


# --------------------------------------------------------------------------- #
# fixtures                                                                      #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def data_source():
    return DataSimFeatureSource()


@pytest.fixture(scope="module")
def local_tracker(tmp_path_factory):
    root = str(tmp_path_factory.mktemp("repro"))
    return repro.ReproTracker(use_mlflow=False, root=root)


@pytest.fixture
def fitted_l3(data_source):
    """A LightGBM L3 scorer trained on shuffled DATA-sim events (positives in both folds)."""
    X, y = data_source.supervised_xy()
    y = pd.Series(np.asarray(y).astype(int), index=X.index)
    rng = np.random.default_rng(1405)
    perm = rng.permutation(len(X))
    sc = LightGBMScorer(n_estimators=150, use_scale_pos_weight=True)
    sc.fit(X.iloc[perm], y.iloc[perm])
    return sc


@pytest.fixture
def fitted_l2(data_source):
    ef = data_source.entity_features()
    ens = L2Ensemble(detectors=[IsolationForestDetector(), EcodDetector()])
    Xpr = L2Ensemble.peer_relative_features(ef)
    ens.fit(Xpr)
    return ens, Xpr


# --------------------------------------------------------------------------- #
# ML-14: layer-parameterized training DAG                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("layer", ["L2", "L3", "L5", "L6"])
def test_dag_runs_end_to_end_and_registers_calibrated(
    layer, data_source, local_tracker
):
    """DAG runs end-to-end for a layer param and registers a calibrated artifact."""
    dag = TrainingDAG(layer, source=data_source, tracker=local_tracker, shadow=True)
    # the ordered steps are exactly the blueprint pipeline
    assert dag.STEPS == (
        "pull",
        "build_features",
        "train",
        "validate",
        "calibrate",
        "register",
        "shadow_deploy",
    )
    res = dag.run()

    assert res.layer == layer
    assert res.calibrated is True, f"{layer} artifact must report calibrated"
    assert res.run.backend == "local"
    assert res.run.model_version  # a registered run with a model version
    assert res.run.dataset_hash and res.run.feature_hash
    assert res.shadow_deployed is True
    # the run is persisted in the local registry
    runs = local_tracker.runs()
    assert any(r["run_id"] == res.run.run_id for r in runs)


def test_dag_supervised_beats_random(data_source, local_tracker):
    """Honest eval: a supervised layer's held-out AUPRC must beat the base rate."""
    res = run_training("L5", source=data_source, tracker=local_tracker)
    assert np.isfinite(res.metrics["auprc"])
    assert res.metrics.get("beats_random") == 1.0


def test_dag_rejects_unknown_layer(data_source):
    with pytest.raises(ValueError):
        TrainingDAG("L9", source=data_source)


def test_airflow_factory_is_scaffold_without_airflow():
    """make_airflow_dag is SCAFFOLD (returns None) when airflow is absent."""
    # airflow is not installed on the reference ML venv -> scaffold path.
    assert make_airflow_dag("L3") is None


def test_dag_does_not_load_torch_for_tree_layers(data_source, local_tracker):
    """Tree layers must not pull torch into the process (macOS dual-libomp guard)."""
    import sys

    run_training("L3", source=data_source, tracker=local_tracker)
    assert "torch" not in sys.modules


# --------------------------------------------------------------------------- #
# ML-15: L2 poisoning guard resists a gradual-shift attack                      #
# --------------------------------------------------------------------------- #
def _poison_events(seed: int = 0) -> tuple[pd.DataFrame, str]:
    """8 benign entities at a stable amount + 1 attacker ramping low-and-slow."""
    rng = np.random.default_rng(seed)
    base = pd.Timestamp("2026-06-01T10:00:00Z")
    rows = []
    for emp_i in range(8):
        emp = f"EMP-{emp_i:04d}"
        for d in range(30):
            amt = max(0.0, rng.normal(1000, 100))
            rows.append(
                {
                    "actor.employee_id": emp,
                    "actor.peer_group": "PG-ops",
                    "object.amount": amt,
                    "ts": (base + pd.Timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            )
    attacker = "EMP-9999"
    for d in range(30):
        amt = 1000 + (8000 - 1000) * (d / 29.0)  # gradual upward drift
        rows.append(
            {
                "actor.employee_id": attacker,
                "actor.peer_group": "PG-ops",
                "object.amount": amt,
                "ts": (base + pd.Timedelta(days=d)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
    return pd.DataFrame(rows), attacker


def test_poisoning_guard_flags_gradual_shift_attacker():
    events, attacker = _poison_events()
    res = LowAndSlowPoisoningGuard().scan(events)
    assert (
        attacker in res.poisoned_entities
    ), "guard must flag the low-and-slow attacker"
    # the change-point + peer-drift signals both fire for the attacker
    assert res.change_magnitude[attacker] >= 1.0
    assert res.peer_drift[attacker] >= 2.5


def test_poisoning_guard_does_not_flag_benign_entities():
    events, attacker = _poison_events()
    res = LowAndSlowPoisoningGuard().scan(events)
    benign = [e for e in res.poisoned_entities if e != attacker]
    assert benign == [], f"benign entities wrongly flagged: {benign}"


def test_poisoning_guard_prevents_threshold_inflation():
    """The guard anchors the 99th-pctile threshold to the clean prefix (resists poisoning)."""
    events, _ = _poison_events()
    res = LowAndSlowPoisoningGuard().scan(events)
    # trusting the poisoned tail would inflate the threshold substantially; the clean
    # index excludes it, so the threshold the guard reports is materially lower.
    assert res.threshold_drift_pct > 20.0
    assert len(res.clean_index) < len(events)


def test_cusum_change_point_detects_upward_drift():
    flat = np.ones(40)
    cp_i, mag = cusum_change_point(flat)
    assert mag == pytest.approx(0.0, abs=1e-6)
    drift = np.concatenate([np.ones(20), np.full(20, 5.0)])
    cp_i2, mag2 = cusum_change_point(drift)
    assert cp_i2 > 0 and mag2 > 1.0


def test_train_l2_persists_thresholds_and_runs_guard(data_source):
    ef = data_source.entity_features()
    res = train_l2(ef, events=data_source.events())
    assert res.calibrated  # = persisted 99th-pctile thresholds
    assert "global_99" in res.thresholds
    assert res.ensemble.is_fitted
    assert res.global_threshold_99 == pytest.approx(res.thresholds["global_99"])


# --------------------------------------------------------------------------- #
# ML-15: L4 keeps deep ONLY if it beats baselines (torch-free baselines)        #
# --------------------------------------------------------------------------- #
def _l4_baselines_and_windows():
    """Torch-free L4 baselines (PCA/IForest/matrix-profile) over a high-signal window set."""
    from ml.layers.l4 import (
        MatrixProfileDetector,
        WindowedIsolationForestDetector,
        WindowedPCADetector,
        build_windows,
    )

    src = SyntheticFeatureSource(n_employees=30, n_days=7, fraud_rate=0.2, seed=1405)
    events = src.events()
    y = _align_labels_to_events(events, src.event_labels())
    ws = build_windows(events, labels=y, window=10)
    base = {}
    for name, det in (
        ("windowed_pca", WindowedPCADetector(window=10)),
        ("windowed_iforest", WindowedIsolationForestDetector(window=10)),
        ("matrix_profile", MatrixProfileDetector(window=10)),
    ):
        det.fit(ws)
        base[name] = det.score_samples(ws)
    return ws, base


def test_l4_gate_keeps_deep_only_if_it_beats_baselines():
    from ml.layers.l4 import keep_if_beats_baselines

    ws, base = _l4_baselines_and_windows()
    assert int(ws.y.sum()) > 0, "need fraud windows to evaluate the gate honestly"

    # a USELESS (random) deep model must NOT be kept
    bad = np.random.default_rng(0).random(len(ws))
    gate_bad = keep_if_beats_baselines(bad, base, ws.y, metric="vus_pr")
    assert gate_bad.keep is False

    # a GOOD deep model (aligned to labels) MUST be kept
    good = ws.y.astype(float) + np.random.default_rng(1).random(len(ws)) * 0.01
    gate_good = keep_if_beats_baselines(good, base, ws.y, metric="vus_pr")
    assert gate_good.keep is True
    assert gate_good.margin > 0


def test_l4_baselines_run_first_have_signal():
    from ml.eval import average_precision

    ws, base = _l4_baselines_and_windows()
    aps = {k: average_precision(ws.y, v) for k, v in base.items()}
    # at least one simple baseline must catch real signal before any deep model
    assert max(aps.values()) > 0.3


# --------------------------------------------------------------------------- #
# ML-16: feedback active-learning + scheduled retrain                           #
# --------------------------------------------------------------------------- #
def test_feedback_active_learning_surfaces_uncertain_and_high_value():
    """Uncertain AND high-value cases sort to the top of the labeling batch."""
    X = pd.DataFrame(
        {"amount": [10.0, 10.0, 5_000_000.0, 5_000_000.0]}, index=["a", "b", "c", "d"]
    )
    # p=0.5 -> max uncertainty; p=0.99 -> low. c is uncertain + high value -> top.
    p = np.array([0.99, 0.01, 0.5, 0.99])
    batch = feedback.select_for_labeling(
        X, p, value=X["amount"].to_numpy(), batch_size=2, value_weight=0.5
    )
    assert "c" in batch.entity_ids  # uncertain + high value
    # pure uncertainty ranks p=0.5 highest
    u = feedback.uncertainty(p)
    assert int(np.argmax(u)) == 2


def test_feedback_retrain_consumes_new_labels(data_source):
    """A scheduled retrain merges EDD dispositions and the A/B is comparable."""
    X, y = data_source.supervised_xy()
    y = pd.Series(np.asarray(y).astype(int), index=X.index)
    ts = pd.to_datetime(
        data_source.events().set_index("event_id")["ts"].reindex(X.index), utc=True
    )

    with tempfile.TemporaryDirectory() as d:
        store = LabelStore(path=os.path.join(d, "disp.jsonl"))
        # disposition flips three previously-benign events to fraud (new labels)
        benign_ids = [str(i) for i in X.index[y.to_numpy() == 0][:3]]
        store.add_disposition(
            Disposition(
                alert_id="a1",
                entity_id="EMP-0001",
                outcome="fraud",
                event_ids=benign_ids,
            )
        )

        merged, n_new = feedback.merge_disposition_labels(y, store)
        assert n_new == 3, "retrain must consume the 3 new EDD labels"
        assert merged.loc[benign_ids].sum() == 3

        rr = feedback.scheduled_retrain(X, y, store, ts=ts, n_estimators=120)
        assert rr.n_new_labels == 3
        assert (
            rr.ab_comparable
        ), "champion vs challenger must be comparable on a shared test"
        assert isinstance(rr.promote, bool)


# --------------------------------------------------------------------------- #
# ML-17: reproducibility — a score is reconstructable                           #
# --------------------------------------------------------------------------- #
def test_repro_score_reconstructable_from_vector_and_version(fitted_l3, data_source):
    X, _ = data_source.supervised_xy()
    with tempfile.TemporaryDirectory() as d:
        ledger = repro.ScoreLedger(path=os.path.join(d, "scores.jsonl"))
        recs = ledger.record_batch(fitted_l3, X.head(8), layer="L3")
        assert len(recs) == 8
        rec = recs[0]
        # the record carries the EXACT feature vector + model_version
        assert rec.model_version == fitted_l3.model_version
        assert len(rec.feature_vector) == X.shape[1]
        # re-running the model on the persisted vector reproduces the score exactly
        rebuilt = repro.reconstruct_score(rec, fitted_l3)
        assert rebuilt == pytest.approx(rec.score, abs=1e-9)
        # and it round-trips from disk
        loaded = ledger.records()
        assert loaded[0].feature_vector == rec.feature_vector


def test_repro_hashes_are_deterministic(data_source):
    ev = data_source.events()
    assert repro.dataset_hash(ev) == repro.dataset_hash(ev)
    cols = ["a", "b", "c"]
    assert repro.feature_hash(cols) == repro.feature_hash(cols)
    assert repro.feature_hash(cols) != repro.feature_hash(["a", "b"])


# --------------------------------------------------------------------------- #
# ML-18: sync fast lane scores L2/L3                                            #
# --------------------------------------------------------------------------- #
def test_sync_fastlane_scores_l2_and_l3_never_blocks(fitted_l2, fitted_l3, data_source):
    ens, Xpr = fitted_l2
    X_event, _ = data_source.supervised_xy()
    emp = (
        data_source.events()
        .set_index("event_id")["actor.employee_id"]
        .reindex(X_event.index)
    )

    lane = SyncFastLane(ens, fitted_l3)
    scores = lane.score(X_entity=Xpr, X_event=X_event, event_entity=emp)

    assert len(scores) == len(Xpr)
    assert all(0.0 <= s.fast_score <= 1.0 for s in scores)
    assert all(not s.blocked for s in scores), "fast lane must never block"
    # both layers contributed model versions
    s0 = scores[0]
    assert "L2_unsupervised" in s0.model_versions and "L3_gbdt" in s0.model_versions
    assert SyncFastLane.within_budget(scores)
    assert SYNC_LATENCY_BUDGET_MS > 0


def test_schedules_sync_async_classification():
    assert is_sync_layer("L2") and is_sync_layer("L3")
    assert is_async_layer("L4") and is_async_layer("L5")
    assert not is_sync_layer("L4")
    # cadence ranges match the blueprint (L4 15min-hourly, L5 hourly-daily)
    assert CADENCES["L4"].min_seconds == 15 * 60
    assert CADENCES["L5"].max_seconds == 24 * 60 * 60


# --------------------------------------------------------------------------- #
# ML-18: async L4/L5 UPGRADE an existing alert (never block)                    #
# --------------------------------------------------------------------------- #
def test_async_upgrades_existing_alert_and_never_blocks():
    alert = {
        "entity_id": "EMP-0001",
        "risk_score": 40,
        "severity": "medium",
        "contributing_layers": ["L2_unsupervised"],
        "reason_codes": [],
        "status": "open",
    }
    up = AsyncUpgrader(layer="L5").upgrade(alert, async_score=0.9)

    assert up.old_risk_score == 40
    assert up.new_risk_score == 90  # upgraded
    assert up.upgraded is True
    assert up.blocked is False
    # the existing alert was upgraded IN PLACE (new layer added, severity raised, still open)
    assert "L5_graph" in alert["contributing_layers"]
    assert alert["risk_score"] == 90
    assert alert["status"] == "open"  # never auto-blocks/closes


def test_async_never_lowers_an_alert():
    alert = {
        "entity_id": "EMP-1",
        "risk_score": 80,
        "contributing_layers": [],
        "reason_codes": [],
    }
    up = AsyncUpgrader(layer="L4").upgrade(alert, async_score=0.1)  # weak async signal
    assert up.new_risk_score == 80  # upgrade-only: never lowers the fast-lane floor
    assert up.blocked is False


# --------------------------------------------------------------------------- #
# ML-18: shadow emits no alerts                                                 #
# --------------------------------------------------------------------------- #
def test_shadow_scoring_emits_no_alerts(fitted_l3, data_source):
    X, y = data_source.supervised_xy()
    y = pd.Series(np.asarray(y).astype(int), index=X.index)
    sink: list = []
    shadow = ShadowScorer(fitted_l3, sink=sink)
    res = shadow.shadow_score(X.head(200), y=y.head(200))

    assert res.alerts_emitted == 0
    assert res.emits_no_alerts is True
    assert res.logged == 200
    # the sink logged scores but every entry is flagged as a non-alert
    assert len(sink) == 200
    assert all(entry["alert"] is False for entry in sink)


# --------------------------------------------------------------------------- #
# ML-18: ClickHouse-backfill re-scoring                                         #
# --------------------------------------------------------------------------- #
def test_backfill_rescores_from_clickhouse_stub(fitted_l2, data_source):
    ens, _ = fitted_l2
    ch = ClickHouseSource(source=data_source)

    def feat(events):
        return L2Ensemble.peer_relative_features(
            featurize.entity_level_features(events)
        )

    with tempfile.TemporaryDirectory() as d:
        ledger = repro.ScoreLedger(path=os.path.join(d, "bf.jsonl"))
        res = backfill_rescore(ch, ens, feat, layer="L2", ledger=ledger)
        assert res.n_rescored > 0
        assert res.model_version == ens.model_version
        # every re-score is persisted with its feature vector (reconstructable)
        assert len(ledger.records()) == res.n_rescored


def test_clickhouse_stub_window_filter(data_source):
    ch = ClickHouseSource(source=data_source)
    full = ch.query_window()
    assert len(full) > 0
    # a far-future lower bound returns nothing
    empty = ch.query_window(start="2099-01-01T00:00:00Z")
    assert len(empty) == 0


# --------------------------------------------------------------------------- #
# ML-19: backtest yields detection-lift + FP-cost                               #
# --------------------------------------------------------------------------- #
def test_backtest_yields_detection_lift_and_fp_cost(data_source):
    _, y = data_source.supervised_xy()
    y = np.asarray(y).astype(int)
    rng = np.random.default_rng(7)
    # a candidate that is mostly right + a little noise
    scores = y * 0.8 + rng.random(len(y)) * 0.2

    res = bt_mod.backtest(y, scores, k=50, threshold=0.5, fp_cost_per_case=1500.0)
    assert res.detection_lift >= 1.0  # beats the random baseline
    assert res.extra_true_positives >= 0
    assert res.fp_cost >= 0.0  # FP-cost estimate present
    assert np.isfinite(res.auprc)
    d = res.to_dict()
    assert {"detection_lift", "fp_cost", "extra_true_positives"} <= set(d)


def test_backtest_compare_candidates_ranks_by_lift(data_source):
    _, y = data_source.supervised_xy()
    y = np.asarray(y).astype(int)
    rng = np.random.default_rng(3)
    good = y * 0.9 + rng.random(len(y)) * 0.1
    poor = rng.random(len(y))
    ranked = bt_mod.compare_candidates(y, {"good": good, "poor": poor}, k=50)
    assert ranked[0].model_version == "good"
    assert ranked[0].detection_lift >= ranked[-1].detection_lift
