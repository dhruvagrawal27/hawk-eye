# Annual Capacity Assessment — Hawk-Eye FY2026 (PLATFORM-31)

> Blueprint **Part 30.2** (capacity management — *annual assessment reviewed by the IT
> Strategy Committee*, an explicit ITGRCA requirement) + **Part 34.2** (capacity & cost
> forecasting). Generated trajectory: `python ops/capacity/capacity_forecast.py`.

## ITSC review record (seeded)
- **Reviewed by:** IT Strategy Committee (ITSC) · **Date:** 2026-05-20 · **Resolution:** ITSC-2026-009
- **Outcome:** Capacity plan **approved**; re-assess annually or on >25% volume change.
- (Mirrors the seeded `approvals` row: artifact_type=`capacity_assessment`, approved.)

## Baseline (pilot)
- Transactions/day: 30,000,000 · Telemetry multiplier: 12× → ~360M events/day.
- Footprint (Lightsail demo): see `python tools/sizing/sizing_calculator.py`.

## 3-year forecast (35% YoY growth)
Run `python ops/capacity/capacity_forecast.py --txns-per-day 30000000 --growth 0.35 --years 3`.
The tool projects Kafka brokers, Flink task managers, ClickHouse shards, GPU pool, Redis, and
the monthly cost trajectory (Lightsail demo + AWS-VPC scale-up) per year.

## Triggers for scale-up (Lightsail → EC2-in-VPC → on-prem)
- Sustained > 50M txns/day OR p99 latency budget pressure → migrate off Lightsail to EC2-in-VPC
  (ADR-0001 scale path); managed MSK/Flink/ElastiCache absorb the streaming load.
- Production go-live / real data → on-prem in-India (Part 9.3, Part 16).

## Error-budget linkage
Capacity is tied to the SLOs (`observability/slo-definitions.yaml`): when the p99-latency or
availability error budget burns, capacity is added BEFORE change velocity resumes (Part 30.2).
