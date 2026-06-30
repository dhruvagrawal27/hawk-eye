# Module: `elasticache` (PLATFORM-7) — SCAFFOLD

Managed **Redis 7.4** (BOM pin 7.4.1) as the online feature store / cache. Primary +
1 replica, **automatic failover + multi-AZ** (HA, Part 30), **encryption in transit
and at rest**, private subnets only, port 6379.

- **Blueprint:** Part 26.1 (Online feature store / cache → ElastiCache for Redis).
- **Migration (Part 26.4):** `ElastiCache → self-hosted Redis 7.4.1`. Same client +
  feature-store contract (Feast online store). See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied. DATABASE owns Redis contents.
