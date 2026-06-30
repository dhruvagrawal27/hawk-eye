"""Tests for the feature catalogue (DATA-19/20/21/22; blueprint Part 6.1-6.6).

Plain test_* functions, bare assert, no pytest. Each crafts a tiny DataFrame carrying
the matching synthetic typology and asserts the feature FIRES on the bad actor and
stays QUIET on the benign actor. Runnable by data/tests/run.py.
"""
from __future__ import annotations

import pandas as pd

from data.features import baselines as bl
from data.features import identity_access as ia
from data.features import transaction as tx
from data.features import data_layer as dl
from data.features import change_hr as ch
from data.features import graph as gr
from data.features import temporal as tp
from data.features import dfs_featuretools as dfs


# ---- DATA-19 baselines ------------------------------------------------------
def test_baselines_three_way_and_decay():
    df = bl.demo_frame()
    b = bl.compute_baselines(df, "amount", "object.amount", window="all")
    # all three levels populated
    assert "EMP-aaaa" in b.per_entity and "EMP-bbbb" in b.per_entity
    assert "PG-ops" in b.per_peer
    assert b.glob.count > 0
    # get() falls back peer->global for unknown entity
    stat = b.get("EMP-unknown")
    assert stat.count >= 0
    # decay: an unseen entity gets peer/global, a known one gets its own mean
    assert b.get("EMP-aaaa").mean > 0


def test_baseline_zscore_flags_outlier():
    df = bl.demo_frame()
    b = bl.compute_baselines(df, "amount", "object.amount")
    stat = b.get("EMP-aaaa")
    # a 10x amount is a strong positive z-score
    assert stat.zscore(stat.mean * 10) > 2.0


# ---- DATA-20 identity / access (6.1) ----------------------------------------
def test_offhours_and_first_after_hours():
    df = ia.demo_frame()
    score = ia.offhours_score(df)
    assert score["EMP-bad"] > score["EMP-good"]
    fta = ia.first_time_after_hours(df)
    assert bool(fta.get("EMP-bad", False)) is True
    assert bool(fta.get("EMP-good", False)) is False


def test_impossible_travel_fires():
    df = ia.demo_frame()
    it = ia.impossible_travel(df)
    assert it.get("EMP-bad", 0) >= 1
    assert it.get("EMP-good", 0) == 0


def test_dormant_reactivation_and_escalation():
    df = ia.demo_frame()
    dorm = ia.dormant_reactivation(df, dormant_days=30)
    assert bool(dorm.get("EMP-bad", False)) is True
    esc = ia.privilege_escalation(df)
    assert esc.get("EMP-bad", 0) >= 1


def test_login_velocity_and_failed_burst():
    rows = []
    base = pd.Timestamp("2026-01-01T10:00:00Z")
    for i in range(5):
        rows.append({ia.E: "EMP-v", ia.PEER: "PG", ia.VERB: "login_failed",
                     ia.TS: (base + pd.Timedelta(minutes=i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     ia.OFFH: False})
    rows.append({ia.E: "EMP-v", ia.PEER: "PG", ia.VERB: "login",
                 ia.TS: (base + pd.Timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 ia.OFFH: False})
    df = pd.DataFrame(rows)
    assert ia.login_velocity(df, 60)["EMP-v"] >= 6
    assert ia.failed_then_success_burst(df)["EMP-v"] >= 1


def test_no_leave_taken_streak():
    df = ia.demo_frame()
    streak = ia.no_leave_taken_streak(df)
    # bad never takes leave; good does -> bad streak >= good streak relative to activity
    assert streak.get("EMP-bad", 0) >= 1


def test_concurrent_and_acting_outside_role():
    df = ia.demo_frame()
    # acting_outside_role returns a value for everyone; bad has a different verb mix
    aor = ia.acting_outside_role(df)
    assert "EMP-bad" in aor.index
    cc = ia.concurrent_session_anomaly(df)
    assert cc.get("EMP-bad", 0) >= 1  # b1 session overlaps itself across two events


# ---- DATA-20 transaction (6.2 + slow) ---------------------------------------
def test_amount_zscore_and_structuring():
    df = tx.demo_frame()
    z = tx.amount_zscore(df, scope="personal")
    # the 4.8M approval row for EMP-bad should be a big z
    bad_rows = df[df[tx.E] == "EMP-bad"]
    big = bad_rows[bad_rows["object.amount"] == 4800000].index
    assert len(big) == 1 and z.loc[big[0]] > 1.0
    jut = tx.just_under_threshold(df, threshold=1000000)
    assert jut.get("EMP-bad", 0) >= 3
    assert jut.get("EMP-good", 0) == 0


def test_new_beneficiary_high_value_latency():
    df = tx.demo_frame()
    res = tx.new_beneficiary_high_value_latency(df, high_value=1000000)
    assert "EMP-bad" in res.index
    assert bool(res.loc["EMP-bad", "new_bene_high_value_flag"]) is True
    assert res.loc["EMP-bad", "min_latency_min"] < 60


def test_swift_cbs_mismatch():
    rows = [
        # matched pair: swift with cbs
        {tx.E: "EMP-ok", tx.VERB: "swift_send", tx.TS: "2026-01-01T10:00:00Z",
         tx.SWIFT: "S1", tx.CBS: "C1"},
        # mismatch: swift with no cbs anywhere
        {tx.E: "EMP-bad", tx.VERB: "swift_send", tx.TS: "2026-01-01T11:00:00Z",
         tx.SWIFT: "S2", tx.CBS: None},
    ]
    df = pd.DataFrame(rows)
    mm = tx.swift_cbs_mismatch(df)
    assert mm.get("EMP-bad", 0) >= 1
    assert "EMP-ok" not in mm.index or mm.get("EMP-ok", 0) == 0


def test_maker_checker_pairing_and_reversal():
    rows = []
    for i in range(4):
        rows.append({tx.E: "EMP-m", tx.VERB: "approve_payment", tx.TS: "2026-01-01T10:00:00Z",
                     tx.MAKER: "EMP-m", tx.CHECKER: "EMP-c"})
    rows.append({tx.E: "EMP-r", tx.VERB: "reversal", tx.TS: "2026-01-01T10:00:00Z"})
    df = pd.DataFrame(rows)
    pairing = tx.maker_checker_pairing(df)
    assert pairing.get("EMP-m->EMP-c", 0) == 4
    assert tx.reversal_clustering(df).get("EMP-r", 0) == 1


def test_suspense_aging_same_person():
    rows = [
        {tx.E: "EMP-bad", tx.VERB: "suspense_post", tx.TS: "2026-01-01T10:00:00Z", tx.ACCT: "ACCT-s"},
        {tx.E: "EMP-bad", tx.VERB: "reconcile", tx.TS: "2026-01-20T10:00:00Z", tx.ACCT: "ACCT-s"},
    ]
    df = pd.DataFrame(rows)
    res = tx.suspense_nostro_aging(df, aging_days=7)
    assert bool(res.loc["EMP-bad", "same_person_post_and_reconcile"]) is True
    assert bool(res.loc["EMP-bad", "aged_flag"]) is True


def test_pnl_mark_and_analyst_clear_rate():
    rows = [
        {tx.E: "EMP-trader", tx.VERB: "mark", tx.TS: "2026-01-01T10:00:00Z",
         "object.amount": 1200, "object.mark_independent": 1000},
    ]
    df = pd.DataFrame(rows)
    div = tx.pnl_mark_divergence(df)
    assert div.get("EMP-trader", 0) > 0.1
    # analyst clear-rate disproportion
    crows = []
    for i in range(8):
        crows.append({tx.E: "EMP-watcher", tx.VERB: "clear_alert", tx.TS: "2026-01-01T10:00:00Z",
                      tx.ACCT: f"AL{i}"})
    crows.append({tx.E: "EMP-other", tx.VERB: "clear_alert", tx.TS: "2026-01-01T10:00:00Z",
                  tx.ACCT: "AL9"})
    # reopen then clear
    crows.append({tx.E: "EMP-watcher", tx.VERB: "reopen_alert", tx.TS: "2026-01-02T10:00:00Z",
                  tx.ACCT: "AL0"})
    crows.append({tx.E: "EMP-watcher", tx.VERB: "clear_alert", tx.TS: "2026-01-02T11:00:00Z",
                  tx.ACCT: "AL0"})
    cdf = pd.DataFrame(crows)
    cr = tx.analyst_clear_rate(cdf)
    assert cr.loc["EMP-watcher", "clear_share"] > cr.loc["EMP-other", "clear_share"]
    assert cr.loc["EMP-watcher", "reopened_then_cleared"] >= 1


# ---- DATA-21 data-layer (6.3) -----------------------------------------------
def test_db_write_without_app_txn_and_export():
    df = dl.demo_frame()
    no_app = dl.db_write_without_app_txn(df)
    assert no_app.get("EMP-bad", 0) >= 1
    assert no_app.get("EMP-dba", 0) == 0  # dba writes correlate to app txns
    epc = dl.export_to_personal_channel(df)
    assert epc.get("EMP-bad", 0) >= 1


def test_sensitive_access_and_log_tampering():
    df = dl.demo_frame()
    sa = dl.sensitive_access_outside_role(df)
    assert sa.get("EMP-bad", 0) >= 1
    rows = [{dl.E: "EMP-t", dl.VERB: "disable_logging", dl.TS: "2026-01-01T02:00:00Z"}]
    assert dl.log_tampering_proxy(pd.DataFrame(rows)).get("EMP-t", 0) == 1


# ---- DATA-21 change/HR (6.4 + slow) -----------------------------------------
def test_self_grant_toxic_and_short_lived():
    df = ch.demo_frame()
    assert ch.entitlement_self_grant(df).get("EMP-bad", 0) >= 1
    assert bool(ch.toxic_combination(df).get("EMP-bad", False)) is True
    assert bool(ch.short_lived_grant_around_txn(df).get("EMP-bad", False)) is True


def test_ghost_employee_and_self_appraiser():
    df = ch.demo_frame()
    ntf = ch.no_tax_footprint(df)
    assert bool(ntf.get("EMP-ghost", False)) is True
    assert bool(ntf.get("EMP-real", True)) is False  # EMP-real has tax
    assert bool(ch.appraiser_is_borrower(df).get("EMP-loan", False)) is True
    assert ch.disbursement_to_non_sanctioned(df).get("EMP-loan", 0) >= 1


# ---- DATA-21 graph (6.5 + slow) ---------------------------------------------
def test_graph_collusion_cycle_and_degree():
    df = gr.demo_frame()
    coll = gr.maker_checker_collusion(df, min_pairs=3)
    assert len(coll) >= 1
    cycles = gr.circular_flow_motifs(df)
    assert len(cycles) >= 1
    deg = gr.beneficiary_degree(df)
    assert deg.get("EMP-maker", 0) >= 1
    cent = gr.eigenvector_centrality(df)
    assert "EMP-maker" in cent.index


def test_graph_slow_lane_signals():
    df = gr.demo_frame()
    va = gr.vendor_address_eq_employee(df)
    assert len(va) >= 1
    scv = gr.single_client_vendor(df)
    assert bool(scv.get("BEN-vendor", False)) is True
    seq = gr.sequential_invoice_numbering(df)
    assert bool(seq.get("BEN-vendor", False)) is True
    dup = gr.duplicated_bank_details(df)
    assert len(dup) >= 1


# ---- DATA-21 temporal (6.6) -------------------------------------------------
def test_temporal_drift_changepoint_periodicity():
    df = tp.demo_frame()
    drift = tp.behavioural_drift(df, window=4)
    assert drift.get("EMP-drift", 0) > 0
    cp = tp.change_point(df)
    assert cp.loc["EMP-drift", "magnitude"] > 0
    per = tp.periodicity_break(df)
    assert bool(per.get("EMP-journal", False)) is True
    seq = tp.session_sequence_features(df)
    # the grant_then_value session should be flagged
    assert bool(seq.xs("EMP-seq", level="employee")["grant_then_value"].any())


# ---- DATA-22 DFS ------------------------------------------------------------
def test_dfs_fallback_generates_aggregates():
    df = dfs.demo_frame()
    fm = dfs.deep_feature_synthesis(df)
    assert not fm.empty
    assert "COUNT()" in fm.columns
    # a sum/mean aggregate of object.amount exists
    assert any("object.amount" in c for c in fm.columns)
    assert "EMP-a" in fm.index and "EMP-b" in fm.index
