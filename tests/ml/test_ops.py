"""Tests for ML-29: operational/business metrics + phasing doc.

No torch / no LightGBM here — pure numpy/pandas, so no OpenMP hazard.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ml.metrics import (
    OpsDashboard,
    alert_volume_vs_capacity,
    cases_surfaced_system_vs_tips,
    compute_ops_dashboard,
    estimated_loss_avoided,
    false_positive_rate,
    mean_time_to_detection,
    mean_time_to_disposition,
    rbi_tat_compliance,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASING_DOC = REPO_ROOT / "docs" / "phasing.md"


# --------------------------------------------------------------------------- #
# alert volume vs capacity                                                    #
# --------------------------------------------------------------------------- #
def test_alert_volume_within_capacity():
    r = alert_volume_vs_capacity(80, 100)
    assert r["utilization"] == pytest.approx(0.8)
    assert r["backlog"] == 0
    assert r["within_capacity"] is True


def test_alert_volume_overflow_and_backlog():
    r = alert_volume_vs_capacity(150, 100)
    assert r["backlog"] == 50
    assert r["within_capacity"] is False
    assert r["utilization"] == pytest.approx(1.5)


def test_alert_volume_zero_capacity_is_inf():
    assert alert_volume_vs_capacity(5, 0)["utilization"] == float("inf")
    assert alert_volume_vs_capacity(0, 0)["utilization"] == 0.0


def test_alert_volume_negative_raises():
    with pytest.raises(ValueError):
        alert_volume_vs_capacity(-1, 10)


# --------------------------------------------------------------------------- #
# MTTD / time-to-disposition                                                  #
# --------------------------------------------------------------------------- #
def test_mttd_from_durations_hours():
    # 1h, 2h, 3h -> mean 2h
    durs = [timedelta(hours=1), timedelta(hours=2), timedelta(hours=3)]
    assert mean_time_to_detection(durations=durs, unit="hours") == pytest.approx(2.0)


def test_mttd_from_timestamps_and_drops_none():
    onset = [datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 0, 0)]
    detect = [datetime(2026, 1, 1, 2, 0), None]  # second never detected -> dropped
    assert mean_time_to_detection(onset, detect, unit="hours") == pytest.approx(2.0)


def test_mttd_empty_is_nan():
    assert math.isnan(mean_time_to_detection(durations=[]))


def test_mttd_bad_unit_raises():
    with pytest.raises(ValueError):
        mean_time_to_detection(durations=[1.0], unit="fortnights")


def test_time_to_disposition_days_default():
    durs = [timedelta(days=2), timedelta(days=4)]
    assert mean_time_to_disposition(durations=durs) == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
# false positive rate                                                         #
# --------------------------------------------------------------------------- #
def test_fpr_from_vectors():
    # benign(0): 4 of them, 1 alerted -> FPR 0.25
    y_true = [0, 0, 0, 0, 1, 1]
    y_alert = [1, 0, 0, 0, 1, 0]
    assert false_positive_rate(y_true, y_alert) == pytest.approx(0.25)


def test_fpr_from_counts():
    assert false_positive_rate(false_positives=2, true_negatives=8) == pytest.approx(
        0.2
    )


def test_fpr_no_benign_is_nan():
    assert math.isnan(false_positive_rate([1, 1], [1, 0]))


# --------------------------------------------------------------------------- #
# RBI <=30-day TAT compliance (the headline acceptance metric)                #
# --------------------------------------------------------------------------- #
def test_rbi_tat_compliance_toy_durations():
    # 3 within 30d, 1 breach -> 0.75
    durs = [10.0, 20.0, 29.0, 45.0]
    r = rbi_tat_compliance(durs, tat_days=30.0)
    assert r["compliance"] == pytest.approx(0.75)
    assert r["n_cases"] == 4
    assert r["n_within"] == 3
    assert r["n_breached"] == 1


def test_rbi_tat_boundary_inclusive():
    # exactly 30 days counts as compliant
    r = rbi_tat_compliance([30.0], tat_days=30.0)
    assert r["compliance"] == pytest.approx(1.0)


def test_rbi_tat_from_timestamps():
    opened = [datetime(2026, 1, 1), datetime(2026, 1, 1)]
    closed = [datetime(2026, 1, 15), datetime(2026, 3, 1)]  # 14d ok, ~59d breach
    r = rbi_tat_compliance(opened_times=opened, closed_times=closed, tat_days=30.0)
    assert r["compliance"] == pytest.approx(0.5)


def test_rbi_tat_open_case_excluded_when_not_breach():
    # open cases are only identifiable via the timestamp path (a bare None
    # duration carries no elapsed info); a still-open case is dropped when
    # count_open_as_breach=False.
    opened = [datetime(2026, 6, 20), datetime(2020, 1, 1)]
    closed = [datetime(2026, 6, 25), None]  # 5d closed; second still open
    r = rbi_tat_compliance(
        opened_times=opened,
        closed_times=closed,
        tat_days=30.0,
        count_open_as_breach=False,
    )
    assert r["n_open_excluded"] == 1
    assert r["n_cases"] == 1
    assert r["compliance"] == pytest.approx(1.0)


def test_rbi_tat_open_case_counts_as_breach_default():
    # a None closed-time with timedelta input: provide already-elapsed durations
    # default count_open_as_breach=True keeps the None duration out (None dropped),
    # so use timestamps to exercise an open long-running case.
    opened = [datetime(2020, 1, 1)]  # very old, still open -> breach
    closed = [None]
    r = rbi_tat_compliance(opened_times=opened, closed_times=closed, tat_days=30.0)
    assert r["n_breached"] == 1
    assert r["compliance"] == pytest.approx(0.0)


def test_rbi_tat_empty_is_nan():
    assert math.isnan(rbi_tat_compliance([])["compliance"])


def test_rbi_tat_bad_window_raises():
    with pytest.raises(ValueError):
        rbi_tat_compliance([1.0], tat_days=0)


# --------------------------------------------------------------------------- #
# estimated loss avoided                                                       #
# --------------------------------------------------------------------------- #
def test_loss_avoided_with_detection_mask():
    # worked-burst exposure 4_800_000 detected, plus an undetected 1_000_000
    exposures = [4_800_000.0, 1_000_000.0]
    detected = [True, False]
    r = estimated_loss_avoided(exposures, detected=detected)
    assert r["loss_avoided"] == pytest.approx(4_800_000.0)
    assert r["total_exposure"] == pytest.approx(5_800_000.0)
    assert r["n_detected"] == 1
    assert r["currency"] == "INR"


def test_loss_avoided_recovery_rate():
    r = estimated_loss_avoided([1_000_000.0], recovery_rate=0.6)
    assert r["loss_avoided"] == pytest.approx(600_000.0)


def test_loss_avoided_bad_recovery_raises():
    with pytest.raises(ValueError):
        estimated_loss_avoided([1.0], recovery_rate=1.5)


# --------------------------------------------------------------------------- #
# cases system vs tips                                                         #
# --------------------------------------------------------------------------- #
def test_cases_system_vs_tips_from_sources():
    src = ["system", "model", "tip", "whistleblower", "ml"]
    r = cases_surfaced_system_vs_tips(src)
    assert r["n_system"] == 3
    assert r["n_tips"] == 2
    assert r["system_share"] == pytest.approx(0.6)


def test_cases_system_vs_tips_from_counts():
    r = cases_surfaced_system_vs_tips(n_system=7, n_tips=3)
    assert r["system_share"] == pytest.approx(0.7)


def test_cases_system_vs_tips_empty_nan():
    assert math.isnan(
        cases_surfaced_system_vs_tips(n_system=0, n_tips=0)["system_share"]
    )


# --------------------------------------------------------------------------- #
# dashboard aggregator — computes ALL listed metrics                          #
# --------------------------------------------------------------------------- #
def test_compute_ops_dashboard_full():
    dash = compute_ops_dashboard(
        n_alerts=120,
        analyst_capacity=100,
        detection_durations=[timedelta(hours=1), timedelta(hours=3)],
        mttd_unit="hours",
        disposition_durations=[timedelta(days=2), timedelta(days=4)],
        y_true=[0, 0, 0, 1],
        y_alert=[1, 0, 0, 1],
        case_durations=[10.0, 20.0, 45.0],
        tat_days=30.0,
        exposures=[4_800_000.0, 1_000_000.0],
        detected=[True, False],
        case_source=["system", "tip", "model"],
    )
    # every metric family present
    for key in (
        "alert_volume",
        "mttd",
        "mean_time_to_disposition",
        "false_positive_rate",
        "rbi_tat_compliance",
        "estimated_loss_avoided",
        "cases_system_vs_tips",
    ):
        assert key in dash

    assert dash["alert_volume"]["backlog"] == 20
    assert dash["mttd"] == pytest.approx(2.0)
    assert dash["mean_time_to_disposition"] == pytest.approx(3.0)
    assert dash["false_positive_rate"] == pytest.approx(1 / 3)
    assert dash["rbi_tat_compliance"]["compliance"] == pytest.approx(2 / 3)
    assert dash["estimated_loss_avoided"]["loss_avoided"] == pytest.approx(4_800_000.0)
    assert dash["cases_system_vs_tips"]["n_system"] == 2


def test_compute_ops_dashboard_partial_inputs_safe():
    # only the mandatory alert-volume inputs; everything else degrades to nan/empty
    dash = compute_ops_dashboard(n_alerts=10, analyst_capacity=20)
    assert dash["alert_volume"]["utilization"] == pytest.approx(0.5)
    assert math.isnan(dash["mttd"])
    assert math.isnan(dash["false_positive_rate"])
    assert math.isnan(dash["rbi_tat_compliance"]["compliance"])
    assert dash["estimated_loss_avoided"]["n_cases"] == 0


def test_ops_dashboard_dataclass_roundtrip():
    d = OpsDashboard(
        alert_volume={},
        mttd=1.0,
        mttd_unit="hours",
        mean_time_to_disposition=2.0,
        disposition_unit="days",
        false_positive_rate=0.1,
        rbi_tat_compliance={},
        estimated_loss_avoided={},
        cases_system_vs_tips={},
    )
    assert d.to_dict()["mttd"] == 1.0


# --------------------------------------------------------------------------- #
# phasing doc                                                                  #
# --------------------------------------------------------------------------- #
def test_phasing_doc_exists():
    assert PHASING_DOC.exists(), f"missing {PHASING_DOC}"


def test_phasing_doc_names_all_four_phases():
    text = PHASING_DOC.read_text()
    for phase in ("Phase 1", "Phase 2", "Phase 3", "Phase 4"):
        assert phase in text, f"phasing doc must name {phase}"


def test_phasing_doc_maps_phases_to_ml_tasks():
    text = PHASING_DOC.read_text()
    # each phase must reference ML-* tasks; check representative anchors
    assert "ML-L2" in text  # phase 1
    assert "ML-L3" in text  # phase 2
    assert "ML-L5" in text  # phase 3
    assert "ML-MRM" in text or "ML-AL" in text  # phase 4
    # the headline operational metric is documented
    assert "TAT compliance" in text


def test_phasing_doc_phase1_mentions_precision_at_k_and_l2():
    text = PHASING_DOC.read_text().lower()
    assert "precision@k" in text
    assert "isolation forest" in text
