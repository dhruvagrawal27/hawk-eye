# HA / Replication configs (PLATFORM-25, blueprint Part 30.1 / Part 9.3)

SCAFFOLD — replication settings for each stateful component. Goes live on a real
multi-AZ (AWS) / multi-DC (on-prem) / multi-rack fabric. RTO/RPO targets:
`ops/dr/rto-rpo-matrix.md`. No single point of failure (ITGRCA).

| Component | File | Strategy |
|---|---|---|
| Kafka | kafka-ha.yaml | RF3, min.insync.replicas=2, rack-aware, multi-broker |
| ClickHouse | clickhouse-ha.xml | sharded + ReplicatedMergeTree (Keeper), hot-cold |
| Redis | redis-ha.conf | primary + replica + Sentinel quorum |
| App/serving | app-ha.yaml | HA pair, pod anti-affinity, PDB, degradation fallback |
