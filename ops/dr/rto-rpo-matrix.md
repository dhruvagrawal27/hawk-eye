# RTO / RPO Matrix (PLATFORM-25, blueprint Part 30.1 / Part 9.3)

> Per-component recovery objectives. HA + multi-AZ (AWS) / multi-DC (on-prem) / multi-rack
> replication; **no single point of failure** (ITGRCA). SCAFFOLD: live targets need a real
> multi-DC fabric. Replication configs: `deploy/ha/`.

| Component | RPO (max data loss) | RTO (max downtime) | Replication / HA | Rationale |
|---|---|---|---|---|
| **Audit log / WORM** | **≈ 0** | minutes | append-only, multi-rack replicated, object-lock | Regulator + natural-justice trail must never lose an entry (Part 19.3) |
| **Alerts topic / Case store (Postgres)** | seconds | **minutes** | Kafka RF3 + Postgres streaming replica | Investigators must keep working; SLA/TAT timers (RBI ≤30d) |
| **Model registry (MLflow + object store)** | minutes | < 1 hour | versioned + object-lock bucket | Reproducibility for audit; not latency-critical |
| **ClickHouse (analytics/history)** | minutes | < 1 hour | sharded + replicated, hot-cold | Drill-down/backfill; tolerates short gaps |
| **Redis / Feast (online features)** | seconds–minutes | minutes | replica + rebuild from Kafka/ClickHouse | Rebuildable; degradation switch covers serving loss |
| **Kafka (transport)** | ≈ 0 (RF3) | minutes | 3–5 brokers, RF3, multi-rack | Ordering + replay; no SPOF |
| **Model serving** | n/a (stateless) | seconds | HA pair + **graceful degradation to L1-rules** | Continuity feature (Part 18) — PLATFORM-4/28 |
| **Governance DB** | minutes | < 1 hour | Postgres replica + nightly backup | Evidence store; go-live gate reads it |

**Targets validated by:** `make dr-drill` (scripted restore drill, measures actual RTO/RPO —
`scripts/dr-drill.sh`) and `make chaos` (kills a broker + serving node; degradation kicks in).
Backups: `ops/backup/` (encrypted, immutable, object-lock). No-SPOF is an explicit ITGRCA
vendor-risk requirement (Part 30.1).
