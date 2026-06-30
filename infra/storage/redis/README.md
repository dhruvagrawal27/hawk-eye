# `infra/storage/redis/` — Online feature store + cache (DATABASE-2)

> **Owner:** DATABASE provides the **physical Redis instance + config + keyspace
> conventions + at-rest note**. **Seam:** DATA defines the feature keys &
> materializes them; ML/BACKEND read. We do **not** define feature logic.
> Blueprint **Part 8** (Feast+Redis online store, l.301), **Part 9.2** (sizing,
> l.359), **Part 9.3** (encryption at rest, l.363).

## Keyspace convention (published in CONTEXT.md)
| DB index | Role | Key format | Eviction |
|---|---|---|---|
| **DB 0** | Feast **online serving** | `"<entity>:<feature>:<window>"` (DATA `config.feature_key`); online entity key `"<entity>:<entity_key>"` | none (volatile-lru only touches TTL'd keys) |
| **DB 1** | **cache** (derived/scratch) | app-defined; set a TTL | volatile-lru |

DATA's online store (`data/feature_store/online_store.py`) already uses the
`<entity>:<entity_key>` / `<entity>:<feature>:<window>` convention — this Redis is
its physical backend (swap its dict fallback → this instance = config change).

## Durability + at-rest
- **AOF (`appendfsync everysec`) + RDB snapshots** → survives restart; supports the
  restore drills (Part 9.3). Files live in `/data`.
- **Encryption at rest:** Redis has none natively → `/data` sits on an **encrypted
  volume** (LUKS locally; KMS/HSM-backed volume in prod — PLATFORM key custody).
- **In transit:** mTLS via the service mesh (PLATFORM).

## AWS swap (1:1)
ElastiCache for Redis with **at-rest (KMS)** + **in-transit** encryption enabled
(`infra/terraform/modules/elasticache`, PLATFORM). Same keyspace + client code.

## Run
```bash
docker compose -f infra/storage/docker-compose.storage.yml up -d redis
redis-cli -a "$REDIS_PASSWORD" -n 0 ping     # DB0 online
redis-cli -a "$REDIS_PASSWORD" -n 1 ping     # DB1 cache
```
