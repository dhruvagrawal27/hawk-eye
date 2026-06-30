# Hawk-Eye — Capacity Sizing & Cost (PLATFORM-5)

> Blueprint **Part 9.2** (sizing) + **Part 26.3** (pilot cost). Generated/validated by
> `tools/sizing/sizing_calculator.py` (unit-tested in `tests/test_sizing_calculator.py`).

## How to use
```bash
python tools/sizing/sizing_calculator.py --txns-per-day 30000000 --telemetry-multiplier 12
python tools/sizing/sizing_calculator.py --txns-per-day 1000000 --telemetry-multiplier 8 --json
```
Inputs: **transactions/day** and the **telemetry multiplier** (5–20× per Part 9.2 — access,
DB-audit, HR, change events typically dwarf transaction volume) and active-entity count.

## What it derives (Part 9.2)
| Output | Rule of thumb encoded |
|---|---|
| **Kafka brokers** | `clamp(ceil(peakMBps / 50), 3, 5)` — RF3 forces a 3-broker floor; partitioned by `entity_id` |
| **Kafka partitions** | `max(6, ceil(peakEvents/s / 5000))` |
| **Flink task managers** | `ceil(peakEvents/s / 20000)` (4 slots each) |
| **ClickHouse shards** | `ceil(hot_compressed_TB / 2)`, ×2 replicas; ~12× compression; 21-day hot tier |
| **GPU pool** | `clamp(ceil(events/day / 5e8), 1, 4)` — train/graph only (Part 9.1) |
| **Redis** | `active_entities × 200 features × 8B × 3 overhead` |

## Reference points (order-of-magnitude)
| Scenario | events/day | Kafka | Flink | ClickHouse | AWS-VPC $/mo | Lightsail $/mo |
|---|---|---|---|---|---|---|
| Large PSB (30M txns × 12) | 360M | 3 brokers | 1 TM | 1 shard ×2 | ~$2,400 | ~$480 |
| Small pilot (1M txns × 8) | 8M | 3 brokers | 1 TM | 1 shard ×2 | ~$2,000 | ~$160 |

> **Deploy-target note (ADR-0001):** the pilot runs on **Lightsail** (fixed-price, far
> cheaper for the demo footprint; no GPU — deep training runs on AWS/on-prem GPU). The
> AWS-VPC column is the **scale-up** path; on-prem is production (Part 9.3, Part 16).
> Costs are ap-south-1 approximations; validate against measured load before procurement.

## Compute placement
See **ADR-0002** + `deploy/profiles/compute-placement.yaml`: CPU for tree-train + all
inference, GPU only for deep sequence/graph training.
