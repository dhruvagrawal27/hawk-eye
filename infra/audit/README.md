# `infra/audit/` — Append-only Kafka audit topics (DATABASE-5)

> **Owner:** DATABASE laptop. **Seam:** DATA/PLATFORM own the Kafka cluster
> runtime; DATABASE owns **only** the audit-topic config + producer schema.
> BACKEND **produces** audit events; the WORM writer (`services/audit/`,
> DATABASE-6) **consumes** and seals them immutably.
> Blueprint **Part 8** (l.311, append-only Kafka audit + WORM), **Part 19.3**
> (l.634, tamper-evident audit of *all* activity incl. investigators).

## Files
| File | Purpose |
|---|---|
| `kafka/audit_event.avsc` | Avro producer schema for one audit envelope. Mirrors `services/audit/audit_schema.py` field-for-field (contract test enforces). |
| `kafka/topics.yaml` | Declarative topic config: `hawkeye.audit` (+`.dlq`) — `cleanup.policy=delete`, `retention.ms=-1` (infinite), compaction **off**, 3 partitions. |
| `create_topics.sh` | Idempotent topic creation against a real Kafka cluster **or** the local single-broker Redpanda fallback. |

## Append-only semantics (why these exact configs)
A WORM/tamper-evident trail must never lose or rewrite a record:
- `cleanup.policy=delete` (**not** `compact`) + `retention.ms=-1` + `retention.bytes=-1`
  → nothing is ever compacted or aged out. The topic is **append-only**.
- `min.insync.replicas>=2` + `unclean.leader.election.enable=false` → no acked
  audit record is ever lost to a failover.
- Key = `target.id` → all events about one alert/entity land on one partition and
  stay **strictly ordered**, which the hash-chain (DATABASE-6) depends on.

## Run it
```bash
# Against the local Redpanda fallback (single broker → RF/ISR = 1):
KAFKA_BOOTSTRAP=localhost:29092 AUDIT_TOPIC_RF=1 AUDIT_MIN_ISR=1 \
  ./infra/audit/create_topics.sh

# Against the DATA/PLATFORM cluster (RF3, ISR2 — the defaults):
KAFKA_BOOTSTRAP=kafka:9092 ./infra/audit/create_topics.sh
```

## AWS / managed-Kafka swap (1:1)
Replace the broker with **MSK** (already stubbed in `infra/terraform/modules/msk`,
PLATFORM): same topic configs apply verbatim. Schema registry → AWS Glue Schema
Registry or keep Apicurio. No producer/consumer code change.

## Seam contract (published in CONTEXT.md)
- Topic: `hawkeye.audit` · key `target.id` · value Avro `audit_event.avsc`.
- Producer leaves `prev_hash`/`record_hash` **empty**; the single-writer WORM
  sink fills them (guarantees a total order + reproducible chain).
- Action enum + the six WORM record classes: see `audit_event.avsc` and
  `services/audit/audit_schema.py`.
