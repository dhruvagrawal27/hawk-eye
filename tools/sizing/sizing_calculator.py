#!/usr/bin/env python3
"""Hawk-Eye sizing & cost calculator (PLATFORM-5, blueprint Part 9.2 + Part 26.3).

Given transactions/day and a telemetry multiplier (5–20× per Part 9.2), derive:
  - Kafka brokers (3–5, RF3, entity-partitioned) + partition count
  - Flink task managers (by event rate / keyed state)
  - ClickHouse shards (sharded+replicated, hot-cold, ~10–20× compression)
  - GPU pool (small, train/graph only) + Redis (active-population online features)
and an AWS monthly $ estimate (m6i/r6i/ElastiCache/g5/RDS/S3, ap-south-1) plus a
Lightsail fixed-price estimate (the chosen pilot deploy target — ADR-0001).

CLI:
    python tools/sizing/sizing_calculator.py --txns-per-day 30000000 --telemetry-multiplier 12
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field

# --- tunable engineering constants (order-of-magnitude, Part 9.2) -------------
BYTES_PER_EVENT = 1500  # security-event JSON, ~1.5 KB
PEAK_FACTOR = 3.0  # peak vs average event rate
PER_BROKER_MBPS = 50  # sustained replicated throughput per Kafka broker
PER_PARTITION_EPS = 5_000  # events/s a single partition handles comfortably
PER_TM_EPS = 20_000  # events/s per Flink task manager (4 slots)
COMPRESSION = 12  # ClickHouse compression (security logs ~10–20×)
HOT_DAYS = 21  # hot tier window (Part 9.2: 14–30 days)
PER_SHARD_TB = 2.0  # hot compressed data per ClickHouse shard
CH_REPLICAS = 2  # replication factor for ClickHouse
FEATURES_PER_ENTITY = 200  # online features held per active entity
BYTES_PER_FEATURE = 8
REDIS_OVERHEAD = 3.0  # Redis memory overhead factor

# --- AWS ap-south-1 on-demand $/hr (approx; order-of-magnitude) ---------------
AWS_HOURLY = {
    "m6i.large": 0.107,
    "m6i.xlarge": 0.214,
    "r6i.xlarge": 0.302,
    "g5.xlarge": 1.212,
    "cache.r6g.large": 0.205,
    "rds.m6i.large": 0.180,
}
HOURS_PER_MONTH = 730
S3_PER_GB_MONTH = 0.025
GPU_DUTY_CYCLE = 0.15  # g5 used ~15% of the month (occasional training)


@dataclass
class Sizing:
    inputs: dict
    events_per_day: int
    avg_events_per_sec: float
    peak_events_per_sec: float
    peak_mb_per_sec: float
    kafka_brokers: int
    kafka_partitions: int
    flink_task_managers: int
    clickhouse_shards: int
    clickhouse_replicas: int
    hot_storage_tb: float
    gpu_count: int
    redis_gb: float
    aws_monthly_usd: dict = field(default_factory=dict)
    lightsail_monthly_usd: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def size(
    txns_per_day: int, telemetry_multiplier: float = 12.0, active_entities: int = 50_000
) -> Sizing:
    if txns_per_day <= 0:
        raise ValueError("txns_per_day must be > 0")
    if not (1 <= telemetry_multiplier <= 50):
        raise ValueError(
            "telemetry_multiplier out of sane range (1–50; Part 9.2 says 5–20)"
        )

    events_per_day = int(txns_per_day * telemetry_multiplier)
    avg_eps = events_per_day / 86_400
    peak_eps = avg_eps * PEAK_FACTOR
    peak_mbps = peak_eps * BYTES_PER_EVENT / 1e6

    kafka_brokers = _clamp(math.ceil(peak_mbps / PER_BROKER_MBPS), 3, 5)  # RF3 needs ≥3
    kafka_partitions = max(6, math.ceil(peak_eps / PER_PARTITION_EPS))
    flink_tms = max(1, math.ceil(peak_eps / PER_TM_EPS))

    raw_bytes_per_day = events_per_day * BYTES_PER_EVENT
    hot_compressed_tb = (raw_bytes_per_day * HOT_DAYS) / COMPRESSION / 1e12
    ch_shards = max(1, math.ceil(hot_compressed_tb / PER_SHARD_TB))

    gpu_count = _clamp(math.ceil(events_per_day / 5e8), 1, 4)
    redis_gb = round(
        active_entities
        * FEATURES_PER_ENTITY
        * BYTES_PER_FEATURE
        * REDIS_OVERHEAD
        / 1e9,
        2,
    )

    s = Sizing(
        inputs={
            "txns_per_day": txns_per_day,
            "telemetry_multiplier": telemetry_multiplier,
            "active_entities": active_entities,
        },
        events_per_day=events_per_day,
        avg_events_per_sec=round(avg_eps, 1),
        peak_events_per_sec=round(peak_eps, 1),
        peak_mb_per_sec=round(peak_mbps, 2),
        kafka_brokers=kafka_brokers,
        kafka_partitions=kafka_partitions,
        flink_task_managers=flink_tms,
        clickhouse_shards=ch_shards,
        clickhouse_replicas=CH_REPLICAS,
        hot_storage_tb=round(hot_compressed_tb, 2),
        gpu_count=gpu_count,
        redis_gb=redis_gb,
    )
    s.aws_monthly_usd = _aws_cost(s)
    s.lightsail_monthly_usd = _lightsail_cost(s)
    s.notes = [
        "Order-of-magnitude per Part 9.2; validate against measured load before procurement.",
        "Kafka RF3 forces a 3-broker floor; partitioned by entity_id (Part 9.2).",
        "ClickHouse hot-cold: hot tier sized here; cold ages to object store (S3/MinIO).",
        "GPU pool is train/graph-only (Part 9.1); inference is CPU. g5 costed at "
        f"{int(GPU_DUTY_CYCLE*100)}% duty cycle (occasional training, Part 26.3).",
        "Lightsail is the chosen pilot deploy target (ADR-0001); AWS-VPC = scale-up path.",
    ]
    return s


def _aws_cost(s: Sizing) -> dict:
    kafka = s.kafka_brokers * AWS_HOURLY["m6i.xlarge"]
    flink = s.flink_task_managers * AWS_HOURLY["m6i.xlarge"]
    clickhouse = s.clickhouse_shards * s.clickhouse_replicas * AWS_HOURLY["r6i.xlarge"]
    serving = 2 * AWS_HOURLY["m6i.xlarge"]  # CPU inference, HA pair
    app = 2 * AWS_HOURLY["m6i.large"]  # FastAPI HA pair
    keycloak = AWS_HOURLY["m6i.large"]
    redis = (
        max(1, math.ceil(s.redis_gb / 13)) * AWS_HOURLY["cache.r6g.large"]
    )  # ~13GB/node
    rds = AWS_HOURLY["rds.m6i.large"]
    gpu = s.gpu_count * AWS_HOURLY["g5.xlarge"] * GPU_DUTY_CYCLE
    compute = {
        "kafka": kafka,
        "flink": flink,
        "clickhouse": clickhouse,
        "serving": serving,
        "app": app,
        "keycloak": keycloak,
        "elasticache_redis": redis,
        "rds_postgres": rds,
        "gpu_training": gpu,
    }
    monthly = {k: round(v * HOURS_PER_MONTH, 0) for k, v in compute.items()}
    # S3: cold storage ≈ a year of compressed events
    cold_gb = (
        s.inputs["txns_per_day"]
        * s.inputs["telemetry_multiplier"]
        * BYTES_PER_EVENT
        * 365
        / COMPRESSION
        / 1e9
    )
    monthly["s3_object_store"] = round(cold_gb * S3_PER_GB_MONTH, 0)
    monthly["TOTAL"] = round(sum(monthly.values()), 0)
    return monthly


def _lightsail_cost(s: Sizing) -> dict:
    # Lightsail fixed-price plans (USD/mo). Pilot demo runs the compose stack on a
    # small number of larger Lightsail instances (ADR-0001).
    plans = {"8GB_2vcpu": 40, "16GB_4vcpu": 80, "32GB_8vcpu": 160}
    # Demo footprint: 1 big node for core infra + 1 for app/serving; +1 if heavy.
    big_nodes = 2 if s.events_per_day < 2e8 else 3
    plan = "16GB_4vcpu" if s.events_per_day < 5e7 else "32GB_8vcpu"
    nodes_cost = big_nodes * plans[plan]
    return {
        "plan_per_node": plan,
        "nodes": big_nodes,
        "node_monthly_each": plans[plan],
        "TOTAL": nodes_cost,
        "note": "Fixed-price demo footprint; no GPU on Lightsail (train elsewhere).",
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Hawk-Eye sizing & cost calculator (Part 9.2 / 26.3)"
    )
    ap.add_argument("--txns-per-day", type=int, default=30_000_000)
    ap.add_argument("--telemetry-multiplier", type=float, default=12.0)
    ap.add_argument("--active-entities", type=int, default=50_000)
    ap.add_argument("--json", action="store_true", help="emit JSON")
    a = ap.parse_args()
    s = size(a.txns_per_day, a.telemetry_multiplier, a.active_entities)
    if a.json:
        print(json.dumps(asdict(s), indent=2))
        return 0
    print(
        f"Hawk-Eye sizing — {a.txns_per_day:,} txns/day × {a.telemetry_multiplier} telemetry"
    )
    print(f"  events/day        : {s.events_per_day:,}")
    print(
        f"  events/s avg/peak : {s.avg_events_per_sec:,} / {s.peak_events_per_sec:,} "
        f"({s.peak_mb_per_sec} MB/s peak)"
    )
    print(
        f"  Kafka             : {s.kafka_brokers} brokers (RF3), {s.kafka_partitions} partitions"
    )
    print(f"  Flink             : {s.flink_task_managers} task managers")
    print(
        f"  ClickHouse        : {s.clickhouse_shards} shards × {s.clickhouse_replicas} replicas "
        f"({s.hot_storage_tb} TB hot)"
    )
    print(f"  GPU pool          : {s.gpu_count} (train/graph only)")
    print(f"  Redis             : {s.redis_gb} GB online features")
    print(
        f"  AWS  $/mo (VPC)   : ${s.aws_monthly_usd['TOTAL']:,.0f}  {s.aws_monthly_usd}"
    )
    print(
        f"  Lightsail $/mo    : ${s.lightsail_monthly_usd['TOTAL']:,.0f}  "
        f"({s.lightsail_monthly_usd['nodes']}× {s.lightsail_monthly_usd['plan_per_node']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
