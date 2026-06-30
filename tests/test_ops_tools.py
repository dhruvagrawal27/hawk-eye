"""Tests for capacity forecast, release governance, and the override/fatigue panel (M3/M4/M5)."""
import datetime as dt

import capacity_forecast as cf
import override_panel as op
import release as rel


# --- capacity (PLATFORM-31) --------------------------------------------------
def test_capacity_forecast_grows():
    fc = cf.forecast(txns_per_day=10_000_000, growth=0.5, years=3)
    assert len(fc) == 4                       # year 0..3
    assert fc[-1]["txns_per_day"] > fc[0]["txns_per_day"]
    assert fc[-1]["events_per_day"] > fc[0]["events_per_day"]


def test_capacity_zero_growth_flat():
    fc = cf.forecast(txns_per_day=5_000_000, growth=0.0, years=2)
    assert fc[0]["txns_per_day"] == fc[-1]["txns_per_day"]


# --- override / fatigue panel (PLATFORM-39) ----------------------------------
def test_override_rate_computation():
    m = op.compute(op.SAMPLE)
    assert 0.0 <= m["override_rate"] <= 1.0
    assert 0.0 <= m["alert_fatigue"] <= 1.0
    assert m["n_ai_fraud"] >= 1


def test_override_rate_all_overridden():
    disp = [{"ai": "fraud", "human": "false_positive", "analyst": "a", "mins": 1} for _ in range(4)]
    m = op.compute(disp)
    assert m["override_rate"] == 1.0
    assert m["alert_fatigue"] == 1.0          # all rushed


# --- release governance (PLATFORM-19) ----------------------------------------
def test_window_check_blocks_outside_window():
    # Wednesday 12:00 UTC is outside the Sat/Sun windows
    wed_noon = dt.datetime(2026, 7, 1, 12, 0, tzinfo=dt.timezone.utc)
    assert rel.window_check(wed_noon)["in_window"] is False


def test_window_check_allows_inside_window():
    # Saturday 20:00 UTC is inside the primary window
    sat_eve = dt.datetime(2026, 7, 4, 20, 0, tzinfo=dt.timezone.utc)
    assert rel.window_check(sat_eve)["in_window"] is True


def test_traceability_loads():
    t = rel.traceability()
    assert "matrix" in t and len(t["matrix"]) >= 5
