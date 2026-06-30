# Online inference topology (BACKEND-13, blueprint Part 18.1)

The production hot path is the Rust gateway (`backend/gateway/`); the Python `app/pipeline/online.py`
is the contract-compatible reference used in tests and local demos. Both implement the same stages.

```
 Kafka(events) ─▶ Flink(enrich + window) ─▶ Redis/Feast(online features)
                                                  │
                                                  ▼
                                       L1 RULES gateway ── hard hit? ─▶ emit HIGH alert immediately (skip ML)
                                                  │  no hard hit
                                                  ▼
                            Model-serving (ONNX): L2 unsupervised + L3 GBDT (+ L4 if window mature)
                                                  │
                                                  ▼
                            L6 FUSION: calibrated 0–100 + severity×confidence + reason codes (TreeSHAP, inline)
                                                  │
                  ┌───────────────────────────────┼───────────────────────────────┐
                  ▼                                ▼                                ▼
        Kafka(alerts) ─▶ Alert/Case store   ClickHouse (event+score+features)   Feature snapshot (repro)
                  │
                  └─ Async: entity/edge ─▶ Graph store ─▶ L5 GNN/XGB-Graph ─▶ may upgrade an existing alert
```

**Owner map (who runs what):**
- DATA — Kafka topics, Flink enrich/window, Feast/Redis materialization.
- BACKEND — L1 rules gateway, model-serving call, L6 fusion, alert emit, idempotency/degradation.
- ML — the L2/L3/L4/L5 artifacts + L6 meta-model + SHAP.
- DATABASE — ClickHouse history, alert/case store, WORM audit.
- PLATFORM — runtime, mesh/mTLS, Kong/APISIX front, observability.

**Invariants (enforced in both implementations):**
- Exactly-once: deterministic `event_id` keying + Flink checkpointing + Kafka transactions (BACKEND-14).
- L1 short-circuit: hard rule hit ⇒ HIGH alert immediately, skip ML (BACKEND-11).
- Graceful degradation: serving down ⇒ L1-rules-only + mark for re-score, never dark (BACKEND-15).
- ALERT-ONLY: emits alerts; never blocks money, never classifies fraud.

**Latency budget (Part 18.1, alert-only, ≤ ~100–300 ms end-to-end):** Kafka+Flink ~10–40 ms ·
Redis ~1–5 ms · L1 rules <5 ms · L2+L3 ONNX ~5–30 ms · TreeSHAP (plain) ~5–20 ms · fusion+emit ~5–10 ms.
