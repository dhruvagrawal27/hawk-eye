"""Unit tests for the sizing calculator (PLATFORM-5, blueprint Part 9.2 / 26.3)."""
import pytest
from sizing_calculator import size, _clamp


def test_kafka_rf3_floor():
    """RF3 forces a 3-broker minimum even at tiny volume (Part 9.2)."""
    s = size(txns_per_day=100_000, telemetry_multiplier=5)
    assert s.kafka_brokers == 3
    assert s.kafka_brokers <= 5  # capped at 5


def test_kafka_caps_at_five():
    s = size(txns_per_day=2_000_000_000, telemetry_multiplier=20)
    assert s.kafka_brokers == 5


def test_events_per_day_math():
    s = size(txns_per_day=10_000_000, telemetry_multiplier=10)
    assert s.events_per_day == 100_000_000
    assert s.peak_events_per_sec == pytest.approx(s.avg_events_per_sec * 3.0, rel=1e-6)


def test_clickhouse_and_redis_scale():
    s = size(txns_per_day=30_000_000, telemetry_multiplier=12, active_entities=50_000)
    assert s.clickhouse_shards >= 1
    assert s.clickhouse_replicas == 2
    assert s.redis_gb > 0
    assert s.gpu_count >= 1 and s.gpu_count <= 4


def test_costs_present_and_positive():
    s = size(txns_per_day=30_000_000, telemetry_multiplier=12)
    assert s.aws_monthly_usd["TOTAL"] > 0
    assert s.lightsail_monthly_usd["TOTAL"] > 0
    # every cost component is non-negative
    assert all(v >= 0 for k, v in s.aws_monthly_usd.items() if isinstance(v, (int, float)))


def test_lightsail_is_cheaper_for_demo():
    """For a small demo footprint, Lightsail fixed-price beats a full VPC fleet."""
    s = size(txns_per_day=1_000_000, telemetry_multiplier=8)
    assert s.lightsail_monthly_usd["TOTAL"] < s.aws_monthly_usd["TOTAL"]


def test_input_validation():
    with pytest.raises(ValueError):
        size(txns_per_day=0)
    with pytest.raises(ValueError):
        size(txns_per_day=1000, telemetry_multiplier=100)


def test_clamp_helper():
    assert _clamp(0, 3, 5) == 3
    assert _clamp(9, 3, 5) == 5
    assert _clamp(4, 3, 5) == 4
