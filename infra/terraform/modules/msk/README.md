# Module: `msk` (PLATFORM-7) — SCAFFOLD

**Amazon MSK** (managed Kafka **3.8.1**, BOM pin) — the event-ingestion backbone.

- One broker per AZ, **KMS-encrypted at rest**, **TLS in transit** (no plaintext),
  private subnets only, JMX + node Prometheus exporters for the observability stack.
- **Blueprint:** Part 26.1 (Ingestion → Amazon MSK).
- **Migration (Part 26.4):** `MSK → self-managed Kafka 3.8.1` (KRaft). Same topics
  (`infra/kafka/topics.yaml`), same producers/consumers — managed MSK is a
  convenience, not lock-in. See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
