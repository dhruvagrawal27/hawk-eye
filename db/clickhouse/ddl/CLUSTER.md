# ClickHouse cluster (replicated) DDL form — DATABASE-3

> Blueprint **Part 9.2** (l.357): a small **sharded + replicated** cluster with
> hot-cold tiering. The canonical `ddl/*.sql` ship the **single-node**
> `ReplacingMergeTree` form (runs on the storage compose with zero Keeper). For
> the cluster, `apply_ddl.sh --mode replicated` (i.e. `CH_ENGINE_MODE=replicated`)
> rewrites them to the replicated form below.

## What the transform does
`apply_ddl.sh` with `CH_ENGINE_MODE=replicated`:
1. `CREATE TABLE hawkeye.events` → `CREATE TABLE hawkeye.events ON CLUSTER hawkeye_cluster`
2. `ENGINE = ReplacingMergeTree(ingested_at)` → `ENGINE = ReplicatedReplacingMergeTree(ingested_at)`

The Replicated engine takes **no explicit ZK path args** because `cluster.xml`
declares server-level defaults:
```xml
<default_replica_path>/clickhouse/tables/{cluster}/{shard}/{database}/{table}</default_replica_path>
<default_replica_name>{replica}</default_replica_name>
```

## Resulting form (example: events)
```sql
CREATE TABLE hawkeye.events ON CLUSTER hawkeye_cluster
( ... same columns ... )
ENGINE = ReplicatedReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(ts)
ORDER BY (actor_employee_id, ts, event_id)
TTL toDateTime(ts) + INTERVAL 30 DAY TO VOLUME 'cold',
    toDateTime(ts) + INTERVAL 365 DAY TO VOLUME 'archive'
SETTINGS storage_policy = 'tiered', index_granularity = 8192;
```

A `Distributed` table fans queries across shards (create per node as needed):
```sql
CREATE TABLE hawkeye.events_dist ON CLUSTER hawkeye_cluster
AS hawkeye.events
ENGINE = Distributed(hawkeye_cluster, hawkeye, events, cityHash64(actor_employee_id));
```

## Topology
`cluster.xml`: **2 shards × 2 replicas**, `internal_replication=true`, ClickHouse
Keeper (Raft) ensemble for coordination. Scale by adding `<shard>` blocks
(document in your capacity plan). Macros `{shard}`/`{replica}` are per-node.

## Residency / DR
Cluster stays **in-India** (Part 9.3). Multi-rack/multi-DC replication via extra
replicas per shard; RPO/RTO + restore drills are PLATFORM's `ops/dr/` (DATABASE
contributes the ClickHouse backup/restore recipe — see `db/README.md`).
