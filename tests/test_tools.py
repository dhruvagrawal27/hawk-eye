"""Unit tests for the staffing calculator, FinOps, and vuln tracker (PLATFORM-39/22)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "security" / "vuln-mgmt"))

import staffing_calculator as sc   # tools/staffing-calculator (conftest path)
import finops                       # tools/finops (conftest path)
import tracker                      # security/vuln-mgmt (path above)


# --- staffing (Erlang) -------------------------------------------------------
def test_staffing_grows_with_volume():
    low = sc.compute(alerts_per_day=50, handling_min=20, sla_hours=8)
    high = sc.compute(alerts_per_day=500, handling_min=20, sla_hours=8)
    assert high.concurrent_agents_required >= low.concurrent_agents_required
    assert high.fte_with_shrinkage > low.fte_with_shrinkage


def test_staffing_meets_target_sl():
    s = sc.compute(alerts_per_day=120, handling_min=25, sla_hours=4, target_sl=0.85)
    assert s.achieved_service_level >= 0.85
    assert 0 < s.occupancy <= 1.0
    assert s.roster["shifts"] == 3


def test_erlang_c_bounds():
    assert sc.erlang_c(0, 5) == 0.0
    assert sc.erlang_c(5, 5) == 1.0      # agents <= load -> always wait
    assert 0.0 < sc.erlang_c(3, 5) < 1.0


def test_staffing_validates_input():
    with pytest.raises(ValueError):
        sc.compute(alerts_per_day=0, handling_min=25, sla_hours=4)


# --- finops ------------------------------------------------------------------
def test_showback_has_fraud_cost_center_and_tags():
    sb = finops.showback()
    assert sb["cost_center"] == "fraud-risk-management"
    assert sb["deploy_target"] == "lightsail"
    assert sb["tags"]["data_residency"] == "in-india"
    assert sb["monthly"]["TOTAL_chosen"] > 0


def test_tco_build_vs_buy():
    t = finops.tco(years=3)
    assert t["verdict"] in ("build", "buy")
    assert t["build_on_lightsail_oss"] > 0 and t["buy_commercial_platform"] > 0


# --- vuln tracker ------------------------------------------------------------
def test_tracker_ingest_and_rank():
    findings = tracker.ingest([])         # sample
    assert findings
    # sorted by severity rank (critical first)
    ranks = [tracker.SEV_RANK.get(f["severity"], 9) for f in findings]
    assert ranks == sorted(ranks)
    for f in findings:
        assert "sla_due" in f and "status" in f


def test_tracker_report_vapt_state():
    tracker.ingest([])
    rep = tracker.report()
    assert rep["vapt_state"] in ("passed", "remediation_required")
    assert "summary" in rep


def test_critical_sla_is_seven_days():
    assert tracker.SLA_DAYS["critical"] == 7
