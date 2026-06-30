# Hawk-Eye — Reference Topology (PLATFORM-4)

> Blueprint **Part 9.1** (reference topology), **Part 18** (online inference + degradation),
> **Part 30.1** (continuity). This reproduces the Part 9.1 diagram exactly, names the
> Kafka topics/streams, and documents the **rules-only graceful-degradation switch**.

## L0 → L7 reference topology (Part 9.1)

```
 CBS/SWIFT/IAM/PAM/DB-audit/HR/IGA   (existing source systems, read-only)
        │  read-only feeds (DATA owns adapters; PLATFORM owns the integration runtime)
        ▼
 Collectors/agents ──►  Kafka cluster (3–5 brokers, RF3; dev: 1 broker)
                        topics: hawkeye.events.l0 (partitioned by entity_id)
        │
        ▼
 Flink cluster  (stateful enrichment + windowed features + CEP rules)   [DATA jobs]
   in:  hawkeye.events.l0      out: hawkeye.events.enriched
        │
        ├───────────────► Redis / Feast (online features, sub-ms)        [DATA/DATABASE]
        │
        ▼
 Model-serving nodes (ONNX/Triton; GPU for train/graph, CPU for inference)  [ML/BACKEND]
   in:  enriched + online features      out: per-layer L2–L6 scores → hawkeye.scores
        │
        ▼
 Risk-fusion service (L6: transparent weighted ensemble → calibrated 0–100)  [BACKEND]
   ──► hawkeye.alerts
        │           ┌──────────────────────────────────────────────────────┐
        ▼           │  DEGRADATION SWITCH (PLATFORM-4, services/degradation- │
 Case/Alert store   │  switch): if ML serving unhealthy → route scoring to   │
 (Postgres)         │  L1-rules-only; mark events → hawkeye.rescore.         │
        │           └──────────────────────────────────────────────────────┘
        ▼
 ClickHouse cluster (hot+cold, history, search, backfill) + audit/WORM       [DATABASE]
   in: hawkeye.alerts, hawkeye.events.*, hawkeye.audit
        │  queries / drill-down
        ▼
 Investigator dashboard (React/TS)   [FRONTEND]  ──► EDD disposition → hawkeye.feedback
        │                                              (active-learning label loop, Part 10)
        ▼
 HITL natural-justice gate (PLATFORM-37): classification held `pending_review` until a
 human approves. ALERT-ONLY: the system NEVER auto-acts (Part 15/16/19.6).

 Cross-cutting (Part 9.1): Kubernetes/Helm · HSM (keys) · Prometheus/Grafana/OTel ·
 MLflow · Airflow/Dagster · network segmentation / zero-trust.
```

## Canonical topics (see `infra/kafka/topics.yaml`)
| Topic | Producer | Consumer | Notes |
|---|---|---|---|
| `hawkeye.events.l0` | collectors (DATA) | Flink, degradation-switch | L0 unified events; partitioned by `entity_id` |
| `hawkeye.events.enriched` | Flink (DATA) | serving/fusion | stateful enrichment + windowed features |
| `hawkeye.scores` | serving (ML) | fusion (BACKEND) | per-layer L2–L6 anomaly scores |
| `hawkeye.alerts` | fusion / degradation-switch | case store, dashboard, ClickHouse | L6 alerts (BACKEND.md §2); 30d retention (RBI TAT) |
| `hawkeye.audit` | all services | WORM sink (DATABASE) | append-only, compacted, never expires (Part 19.3) |
| `hawkeye.feedback` | dashboard (FRONTEND/BACKEND) | retraining (ML) | EDD dispositions → labels |
| `hawkeye.rescore` | degradation-switch | fusion (BACKEND) | events scored rules-only, re-scored when ML recovers |
| `hawkeye.dlq` | any consumer | ops | poison-message dead-letter (Part 32.2) |

## Graceful degradation (the continuity feature)
`services/degradation-switch` (REAL) probes ML-serving health. **Healthy** → full L1+L2–L6
fusion. **Unhealthy / forced** → **L1-rules-only** (BACKEND's BRE; the switch ships a
labelled fallback subset). Every rules-only event is published to `hawkeye.rescore` so it
is re-scored when serving recovers — **nothing is dropped**. This is simultaneously the
Part 18 online-continuity feature and the Part 30.1 BCP graceful-degradation mode, and it
is the software proof of the **ALERT-ONLY** golden rule.

- Demo: `make degradation-demo`
- Smoke: `make topology-smoke` (flows a synthetic L0 event → alert)
