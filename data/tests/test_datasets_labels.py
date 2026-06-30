"""Tests for DATA-12 loaders, DATA-24 splits, DATA-23 label store.

Plain test_* functions, bare asserts, runnable by data/tests/run.py (no pytest).
Each builds its own tiny inputs or uses a module demo() helper. Fast (small N).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from data.datasets import splits
from data.datasets.loaders import (
    CertLoader, IeeeCisLoader, UlbLoader, PaySimLoader, EllipticLoader, SpediaLoader,
)
from data.labels.label_store import LabelStore, demo_store
from data.schemas.label import Label


# --------------------------------------------------------------------------- #
# DATA-24: temporal split puts later ts in test and rejects random            #
# --------------------------------------------------------------------------- #
def test_temporal_split_future_in_test():
    df = splits.demo()
    train, test = splits.temporal_split(df, "ts", test_frac=0.25)
    assert len(train) > 0 and len(test) > 0
    assert splits.is_temporal_split(train, test, "ts")
    # every test timestamp is >= every train timestamp
    assert max(pd.to_datetime(train["ts"])) <= min(pd.to_datetime(test["ts"]))


def test_random_split_is_rejected():
    df = splits.demo()
    train, test = splits.make_random_split(df, test_frac=0.25, seed=7)
    rejected = False
    try:
        splits.assert_not_random_split(train, test, "ts")
    except AssertionError:
        rejected = True
    assert rejected, "random split for fraud data must be rejected (Part 21.4)"


def test_temporal_split_passes_the_guard():
    df = splits.demo()
    train, test = splits.temporal_split(df, "ts", test_frac=0.25)
    # the guard must NOT raise for a proper temporal split
    splits.assert_not_random_split(train, test, "ts")


# --------------------------------------------------------------------------- #
# DATA-24: remove_leaky_features drops an injected leaky column                #
# --------------------------------------------------------------------------- #
def test_remove_injected_leaky_column():
    df = splits.demo()  # has 'leaky_balance' == label
    cleaned, report = splits.remove_leaky_features(df, "label", return_report=True)
    assert "leaky_balance" in report, f"leaky col not detected: {report}"
    assert "leaky_balance" not in cleaned.columns
    assert "label" in cleaned.columns  # label kept
    # a non-leaky column survives
    assert "amount" in cleaned.columns


def test_paysim_balance_columns_flagged_as_leaky():
    df = PaySimLoader().synthetic()
    report = splits.detect_leaky_features(
        df, "isFraud", known_leaky=PaySimLoader.leaky_cols
    )
    for col in PaySimLoader.leaky_cols:
        assert col in report, f"PaySim leaky balance col {col} not flagged"


def test_entity_disjoint_split():
    df = splits.demo()
    train, test = splits.entity_disjoint_split(df, "entity", test_frac=0.34)
    assert len(train) > 0 and len(test) > 0
    assert splits.is_entity_disjoint(train, test, "entity")


# --------------------------------------------------------------------------- #
# DATA-12: loaders run offline (synthetic stand-ins)                          #
# --------------------------------------------------------------------------- #
def test_cert_loader_synthetic_emits_l0_and_labels():
    events, labels = CertLoader().synthetic()
    assert len(events) > 0 and len(labels) > 0
    # events validate as L0 (have employee + verb)
    d = events[0].to_dict()
    assert d["actor"]["employee_id"]
    assert d["action"]["verb"]
    # labels reference real event_ids and are positive insider labels
    eids = {e.event_id for e in events}
    assert all(l.event_id in eids for l in labels)
    assert all(l.is_fraud for l in labels)


def test_tabular_loaders_have_label_column():
    assert IeeeCisLoader().synthetic()[IeeeCisLoader.label_col].nunique() >= 1
    assert UlbLoader().synthetic()[UlbLoader.label_col].sum() >= 1  # at least one fraud
    assert SpediaLoader().synthetic()[SpediaLoader.label_col].notna().all()
    paysim = PaySimLoader().synthetic()
    assert paysim["isFraud"].sum() >= 1


def test_paysim_to_l0_maps_events():
    df = PaySimLoader().synthetic(n=20)
    evs = PaySimLoader().to_l0(df)
    assert len(evs) == len(df)
    assert evs[0].object.currency == "INR"


def test_elliptic_graph_is_pu_shaped():
    g = EllipticLoader().synthetic()
    nodes, edges = g["nodes"], g["edges"]
    assert {"txId", "class"}.issubset(nodes.columns)
    assert (nodes["class"] == -1).any()  # unlabelled majority present (PU setting)
    assert {"txId1", "txId2"}.issubset(edges.columns)


def test_loaders_document_no_drop_in_model():
    # the honest Part-5.3 stance is stated in each loader MODULE docstring
    import importlib
    for mod_name in ("cert", "ieee_cis", "ulb", "paysim", "elliptic", "spedia"):
        mod = importlib.import_module(f"data.datasets.loaders.{mod_name}")
        assert "No drop-in pre-trained model" in (mod.__doc__ or ""), mod_name


# --------------------------------------------------------------------------- #
# DATA-23: LabelStore.merge yields labels from all 4 sources                  #
# --------------------------------------------------------------------------- #
def test_label_store_merges_all_four_sources():
    store = demo_store()
    present = store.sources_present()
    for src in ("gold", "weak", "synthetic", "edd"):
        assert src in present, f"missing label source {src}: {present}"
    merged = store.merge()
    assert len(merged) >= 4
    merged_sources = {l.label_source for l in merged}
    # every source contributes at least one surviving label (disjoint event_ids in demo)
    for src in ("gold", "weak", "synthetic", "edd"):
        assert src in merged_sources, f"{src} dropped from merge: {merged_sources}"


def test_edd_ingest_matches_backend_md_section5_shape():
    store = LabelStore()
    # BACKEND.md §5 REQUEST shape
    payload = {
        "alert_id": "alr_3d7e22", "outcome": "fraud",
        "notes": "Confirmed shell beneficiary; maker-checker collusion.",
        "evidence_ids": ["evt_8f2a1c90"],
    }
    lab = store.ingest_edd_disposition(payload)
    assert isinstance(lab, Label)
    assert lab.event_id == "evt_8f2a1c90"
    assert lab.is_fraud is True
    assert lab.label_source == "edd"
    # false_positive -> a benign label
    fp = store.ingest_edd_disposition({"outcome": "false_positive",
                                       "evidence_ids": ["evt_fp01"]})
    assert fp is not None and fp.is_fraud is False
    # inconclusive -> NO label written (stays in PU pool)
    none_lab = store.ingest_edd_disposition({"outcome": "inconclusive",
                                             "evidence_ids": ["evt_inc01"]})
    assert none_lab is None
    assert "evt_inc01" not in store.labelled_event_ids()


def test_edd_rejects_unknown_outcome():
    store = LabelStore()
    raised = False
    try:
        store.ingest_edd_disposition({"outcome": "maybe", "evidence_ids": ["evt_x"]})
    except ValueError:
        raised = True
    assert raised


def test_edd_response_fixture_shape():
    fx = LabelStore.edd_response_fixture()
    for k in ("alert_id", "status", "label_written", "feedback_queued_for_retraining", "audit_id"):
        assert k in fx


# --------------------------------------------------------------------------- #
# DATA-23: weak labelling + PU/semi-supervised hooks                          #
# --------------------------------------------------------------------------- #
def test_weak_labelling_fires_on_rule_hit():
    store = LabelStore()
    events = [
        {"event_id": "evt_w1",
         "actor": {"employee_id": "EMP-1", "notice_period": True},
         "action": {"verb": "export"}, "object": {}, "context": {}},
        {"event_id": "evt_w2",
         "actor": {"employee_id": "EMP-2"},
         "action": {"verb": "login"}, "object": {}, "context": {}},  # abstain
    ]
    n = store.add_weak_labels(store.default_labeling_functions(), events)
    assert n == 1  # only the leaver-export event gets a weak label
    assert store.get("evt_w1").is_fraud is True
    assert store.get("evt_w2") is None  # abstain -> unlabelled


def test_pu_reliable_negatives_excludes_positives():
    from data.labels.label_store import pu_reliable_negatives
    all_ids = [f"e{i}" for i in range(10)]
    pos = {"e0", "e1"}
    negs = pu_reliable_negatives(all_ids, pos, negative_fraction=0.5)
    assert negs and all(n not in pos for n in negs)
    # with scores, lowest-scoring unlabelled chosen first
    scores = {e: float(i) for i, e in enumerate(all_ids)}
    negs2 = pu_reliable_negatives(all_ids, pos, scores=scores, negative_fraction=0.25)
    assert "e2" in negs2  # lowest-scoring non-positive


def test_self_training_pseudolabels_threshold():
    from data.labels.label_store import self_training_pseudolabels
    scores = {"a": 0.95, "b": 0.05, "c": 0.5, "d": 0.99}
    pseudo = self_training_pseudolabels(scores, labelled_ids={"d"}, high=0.9, low=0.1)
    assert pseudo["a"] is True
    assert pseudo["b"] is False
    assert "c" not in pseudo   # mid-confidence stays unlabelled
    assert "d" not in pseudo   # already labelled
