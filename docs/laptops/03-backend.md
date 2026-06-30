# Laptop 03 — BACKEND — Working Log

> Your **own** file. Read `CONTEXT.md`, `BACKEND.md`, `TODO.md` first; append cross-cutting decisions to `CONTEXT.md`. **You also OWN `BACKEND.md`** — keep it in sync with the real API. Full brief: [prompts/03_BACKEND.md](../../prompts/03_BACKEND.md).

**Ownership:** BACKEND owns `BACKEND.md`; everyone else reads it to integrate. If a non-BACKEND laptop needs a contract change, they propose it in `CONTEXT.md` and tag BACKEND; I (BACKEND) make the edit.

## Status
- Branch: `hawk-eye/backend` · Owns: `backend/` + `BACKEND.md`
- **All 29 tasks (BACKEND-1..29) complete.** 102 Python tests green (unit + integration + contract). `openapi.json` generated (30 routes). Rust `gateway/` crate written.

## Decisions
- **Package layout.** API app at `services/api/app` (top-level package `app`); cross-cutting packages at `backend/` root (`rules_engine`, `serving`, `fusion`, `regulatory`, `reliability`, `integrations`, `compliance`). Both roots on the import path via `pyproject` `pythonpath` + `conftest.py` + `run_api.py`. Keeps `rules_engine`/`serving`/`fusion` runnable inside the Rust/Python hot path and in tests without importing FastAPI.
- **Decoupling.** `rules_engine` and the gateway operate on plain `dict` events + a feature `dict` (no app import) so the same logic runs in the API, in batch, and in the Rust crate.
- **Prometheus.** Hand-rolled stdlib exposition (`app/observability/metrics.py`) — no `prometheus_client` runtime dependency; swappable later.
- **JWT.** Authlib (`authlib.jose`) — local HS256 dev tokens + Keycloak RS256/JWKS path. Short-lived access (15 min), rotating refresh.
- **Online path.** Two implementations of the same Part 18.1 topology: the **Rust** crate (`gateway/`, production hot path) and the **Python** reference (`app/pipeline/online.py`, tested). Both enforce idempotency, L1 short-circuit, graceful degradation, ALERT-ONLY.
- **SLA.** `sla_due_ts` = created + RBI 30-day cap (matches the Part 24.5b example exactly); tighter per-severity internal TATs (`internal_tat_days`) drive prioritization/routing, not the regulatory deadline.

## Files created (high level)
- M1: `app/main.py`, `app/config.py`, `app/observability/*`, `app/auth/*` (oidc, rbac, sod, case_scope, deps, opa/rbac.rego), `app/schemas/*`.
- M2: `rules_engine/*` (engine, loader, named_rules, privileged, sod_matrix, rules/*.yaml, opa/entitlement.rego).
- M3: `serving/*` (registry, loader, runtime, server, stubs), `fusion/*` (service, calibration, treeshap, reason_codes), `reliability/*`, `app/pipeline/online.py`, `app/clients/*`, `gateway/` (Rust crate).
- M4: `app/pii/*` (tokenizer, vault, crypto), `app/routes/*`, `app/workflow/escalation.py`, `app/audit/writer.py`, `app/store/*`.
- M5: `regulatory/*` (ews, rfa, crilc, fmr, cfr, slow_lane), `integrations/siem.py`, `compliance/dpdp.py`, `app/routes/{report,compliance}_routes.py`, `gateway_config/kong.yaml`, `deploy/*`.
- Tests: `tests/{unit,integration,contract}/*` (102 tests).

## Blueprint validation (Part → task → ✓)
- ✅ Part 24.1 — 8×9 RBAC encoded exactly + SoD + separate audited unmask → `app/auth/rbac.py`, `sod.py`; `test_rbac.py`.
- ✅ Part 24.2 — every API route built (auth, alerts, entities×4, explanations, narratives, unmask, rules, models×2, drift/metrics, feedback, reports×2, audit, admin×2, health/metrics) → `openapi.json`; `test_routes_rbac.py`, `test_health_metrics.py`.
- ✅ Part 24.5(b)(c) — alert + disposition payloads exact → `app/schemas/{alerts,disposition}.py`; `test_alert_contract.py`, `test_disposition_contract.py`.
- ✅ Part 3.1 / 20.1 — L1 BRE, all named rules, versioned/hot-reloadable, cold-start → `rules_engine/`; `test_rules_engine.py`.
- ✅ Part 3.4 — SoD/toxic-combination matrix + OPA entitlement → `rules_engine/sod_matrix.py`, `opa/entitlement.rego`; `test_sod_matrix.py`.
- ✅ Part 2 / 19.3 — privileged-session, DB-write-without-app-txn, self-grant → `rules_engine/privileged.py`; `test_privileged.py`.
- ✅ Part 31.3 — four-eyes change-controlled rule CRUD → `app/routes/rules_routes.py`; `test_routes_rbac.py::test_four_eyes_rule_change`.
- ✅ Part 18.1/18.3/23.4 — online topology, serving, L1 short-circuit, L6 fusion + plain TreeSHAP, idempotency, graceful degradation, registry-driven signed load + canary, latency budget → `serving/`, `fusion/`, `app/pipeline/online.py`, `gateway/`; `test_worked_burst.py`, `test_idempotency.py`, `test_graceful_degradation.py`, `test_serving_loader.py`, `test_latency.py`.
- ✅ Part 25.3/25.5 — HMAC-SHA256 tokenization + re-id vault + audited unmask + before-egress → `app/pii/*`; `test_tokenizer.py`.
- ✅ Part 11 — triage ranking, entity-360 timeline, explanation (SHAP+rule+attention+graph), peers → `app/routes/{alert,entity,explanation}_routes.py`.
- ✅ Part 16 / 19.6 / 29.2 — EDD disposition→label loop, alert-only, block-request never auto, watch-the-watchers → `disposition_routes.py`, `audit/writer.py`.
- ✅ Part 33.3 — severity escalation + SLA/TAT (RBI ≤30-day) + `sla_due_ts` → `app/workflow/escalation.py`; `test_escalation_fusion.py`.
- ✅ Part 16 — EWS/RFA/CRILC(₹3cr/7d/180d)/FMR/CFR/DAMI + slow-lane four typologies + export routes → `regulatory/`; `test_regulatory.py`.
- ✅ Part 9.3 — bi-directional SIEM → `integrations/siem.py` (SCAFFOLD).
- ✅ Part 32.1 — API gateway front → `gateway_config/kong.yaml`.
- ✅ Part 28.1 — DPDP cross-border + data-principal rights → `compliance/dpdp.py` (SCAFFOLD).

## Deviations / assumptions
- **Python 3.13 / FastAPI 0.135 locally** vs Part 24.3 pins (3.12 / 0.115). `pyproject.toml` declares the blueprint target pins (`>=0.115,<1.0` etc.); code is 3.12-compatible. CI pins exact patches + generates the lockfile.
- **ruff / black / mypy / cargo not installed locally** — code written to those conventions; the §8 commands run in PLATFORM's CI harness. `cargo test` for `gateway/` is deferred to CI (the crate has unit tests in every module).
- **Prometheus exposition hand-rolled** (no `prometheus_client` dep) — documented, swappable.
- **`/events/ingest`** added as a synthetic ingestion entry (the production entry is Kafka via the Rust gateway) — clearly marked internal.

## Stubs created for not-yet-built dependencies (swap-in needs no API change)
- `# STUB: DATA` — `app/clients/feature_client.py` (Feast/Redis online features).
- `# STUB: ML` — `serving/stubs/deterministic_models.py` (signed ONNX L2/L3/L4), `fusion/{treeshap,calibration,service}.py` (L6 meta + calibrator + TreeSHAP), `app/clients/narrative_client.py` (`narrate()`).
- `# STUB: DATABASE` — `app/store/*` (Postgres cases/users/rules/vault + ClickHouse history), `app/audit/writer.py` (WORM), `serving/registry.py` (model registry layout).
- `# STUB: PLATFORM` — Vault key custody (read from env), Keycloak (local HS256 fallback), Kong runtime.

## Blockers (mirror in TODO.md §7 + CONTEXT.md)
- None blocking. Awaiting (non-blocking, contract honored via stubs): DATA Feast keys (§1a), ML signed ONNX + `narrate()`, DATABASE WORM + registry + DDL, PLATFORM Keycloak/Vault/Kong.

## Session log (newest first)
- 2026-06-30 — Built BACKEND-1..29 end-to-end on synthetic data; 102 tests green; `BACKEND.md`/`TODO.md`/`CONTEXT.md` synced; `openapi.json` generated; Rust gateway crate written.
