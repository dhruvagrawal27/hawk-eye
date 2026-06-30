# degradation-switch (PLATFORM-4 / PLATFORM-28)

The **REAL** graceful-degradation control plane. Blueprint **Part 18** (rules-only
continuity) + **Part 30.1** (BCP graceful degradation). Proves golden rule #1
(**ALERT-ONLY**): it produces alerts for a human to triage and **never** an action.

## What it does
- Probes ML-serving health (`ML_SERVING_HEALTH_URL`). Healthy → **full** fusion
  (L1 rules + L2–L6 model scores). Unhealthy, or `DEGRADATION_FORCE_RULES_ONLY=true`,
  or `POST /admin/force {forced:true}` → **L1-rules-only** fallback.
- In rules-only mode it still scores via the L1 typology subset (`app/rules.py`) and
  **marks each event for re-scoring** (`hawkeye.rescore`) so nothing is dropped when
  ML serving recovers.
- Optional Kafka worker (`ENABLE_KAFKA_WORKER=true`) runs the real topology hop
  `events.l0 → score → alerts` so the switch participates in the live pipeline.

## Ownership boundary
BACKEND owns the production rules/BRE + fusion (Part 11/18). This service
*containerizes/deploys* them and owns only the **fallback decision + routing**;
`app/rules.py` is a clearly-labelled continuity subset, not the production engine.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| GET | `/mode` | `{mode, ml_serving_healthy, forced}` |
| POST | `/score` | `{event, layer_scores?}` → `{mode, alert\|null}` |
| POST | `/admin/force` | toggle forced rules-only (audited; PAM-gated in prod) |
| GET | `/metrics` | Prometheus |

## Demo
`make degradation-demo` kills ML serving and shows scoring continue rules-only.
`make topology-smoke` flows a synthetic L0 event end-to-end to an alert.
