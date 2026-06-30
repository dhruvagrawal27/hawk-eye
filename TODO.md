# TODO.md — Shared Task Board

> Each laptop keeps its own section current (`[ ]` todo, `[~]` in-progress, `[x]` done, `[!]` blocked). Task IDs and the full task lists live in [`BUILD_PLAN.md`](BUILD_PLAN.md) and in each laptop's prompt under `prompts/`. **A task is `[x]` only when its blueprint requirement is validated.** Put cross-laptop blockers in §7.

## 1. 📥 DATA (28 tasks — see prompts/01_DATA.md) — **M1–M5 built, tested & VERIFIED (28/28 tasks, 97/97 tests), branch hawk-eye/data**
- [x] M1 Foundations: L0 schema (+avsc/sample), schema registry, Kafka(topics+clients), Flink(window job), normalizer, Feast+Redis (pure-python fallbacks for infra)
- [x] M2 Simulator + public datasets: 12-typology red-team library (8 fast + 4 slow), ground-truth labels, worked burst, augmentation, 6 dataset loaders
- [x] M3 Source connectors (SCAFFOLD: CBS/payments/IAM-PAM/DLP-DBaudit/HR-IGA/real-telemetry + mock fixtures) + reliability/dedupe/DLQ/count-recon + [x] SWIFT↔CBS recon (REAL)
- [x] M4 Feature engineering catalogue (every 6.1–6.6 + slow-lane) + three-way baselines + DFS + online/offline parity
- [~] M5 Governance/quality/lineage/MDM/retention (REAL); label store: gold=MOCK, EDD source-4 **[!] stubbed — awaits BACKEND `POST /alerts/{id}/disposition`**

## 2. 🤖 ML (29 tasks — see prompts/02_ML.md) — **✅ COMPLETE on hawk-eye/ml. All 29 tasks; 250 tests pass / 0 fail (.mlvenv py3.13, `python -m ml.tests.run`). End-to-end demo runs (`python -m ml.demo`).**
- [x] M1 Foundations (ML-1/2) + L2 unsupervised (ML-3: IF/ECOD/COPOD/AE/OCSVM via PyOD+torch, ensemble)
- [x] M2 L3 GBDT (ML-4) + L4 sequence (ML-5, REAL torch) + L5 graph (ML-6, REAL PyG, GADBench lift) + L6 fusion (ML-7→BACKEND §2 alert) + strategies (ML-8) + design (ML-9) + narrative gateway (ML-10..13: failover/grounding/audit/attestation/POST·narratives)
- [x] M3 Pipelines (ML-14..19): DAG, per-layer trainers, EDD feedback+active-learning, repro/ledger, sync/async/shadow/backfill inference, backtest
- [x] M4 MLOps (ML-20..24): registry+inventory, champion/challenger+shadow+canary+signed-load+auto-rollback, PSI/KS+concept drift+threshold governance, model cards/MRM, SIMULATED validation sign-off (MOCK)
- [x] M5 fairness (ML-25/26), robustness (ML-27), CI suites (ML-28, fairness-gated), phasing+ops metrics incl. RBI TAT (ML-29)
- **SCAFFOLD** (need real keys/HW): live NEAR AI/Groq calls + TEE attestation. **MOCK**: independent human validator sign-off.

## 3. ⚙️ BACKEND (29 tasks — see prompts/03_BACKEND.md) — also owns BACKEND.md
- [x] M1 FastAPI app, auth/RBAC (Keycloak/JWT), health/metrics — BACKEND-1..4 (Part 24.1/24.2/24.5)
- [x] M2 L1 rules/BRE + SoD/toxic-combination matrix engine — BACKEND-5..8 (Part 3.1/3.4/20.1/31.3)
- [x] M3 Risk-fusion + model serving (signed loader/canary) + Rust hot-path + reliability — BACKEND-9..16 (Part 18.1/18.3/23.4)
- [x] M4 Alert/entity/explanation routes, EDD feedback loop, PII tokenization + re-id vault, audit/admin/escalation — BACKEND-17..23 (Part 11/16/19.3/25.3/29.2/33.3)
- [x] M5 EWS/RFA/CRILC/FMR/CFR generators + slow-lane + export routes + SIEM + DPDP + gateway front — BACKEND-24..29 (Part 16/9.3/28.1/32.1)
  - SCAFFOLD (code-complete on synthetic; await live external resource): BACKEND-24/25 (RBI submission channel), 27 (live SIEM), 29 (TEE hardware + legal jurisdiction).
  - 102 backend tests green (unit + integration + contract); `openapi.json` generated; `BACKEND.md` synced. Rust `gateway/` crate written (cargo not installed locally → `cargo test` deferred to PLATFORM CI).

## 4. 🖥️ FRONTEND (13 tasks — see prompts/04_FRONTEND.md) — **M1–M4 built, REAL, all §8 gates green (tsc/eslint/prettier/vitest 112/Playwright e2e 3/build), branch hawk-eye/frontend**
- [x] M1 App shell, SSO/login (OIDC PKCE + mock SSO), RBAC routing (Part 24.1 8×9 matrix + SoD), typed API client, MSW mocks, audited `<MaskedPII>` (FRONTEND-1,2,3)
- [x] M2 Triage queue (ranked risk×exposure×confidence, dedup, SLA timer, claim) + alert/case detail + case management + entity-360 timeline (FRONTEND-4,5,6,7)
- [x] M3 Explanation panel (SHAP + rule provenance + LAXCAT attention + AI narrative w/ TEE badge) + graph/link view (Cytoscape, collusion/ring/GNNExplainer) + peer comparison + EDD action panel (alert-only, audit+relabel) (FRONTEND-8,9,10,11)
- [x] M4 Compliance (rules four-eyes change-control + EWS/RFA coverage + CRILC/FMR export) + auditor + model-engineer + admin (Grafana embed) + reporting/board-KRI views (FRONTEND-12,13)
- Renders the Part 24.5 worked burst end-to-end on MSW (`VITE_USE_MOCKS=true`); contract needs flagged in CONTEXT.md (newest entry) — `[FE-proposed]` bodies + `/cases`, `/reports/ews-coverage`, `/reports/kris` tagged BACKEND.

## 5. 🗄️ DATABASE (9 tasks — see prompts/05_DATABASE.md) — **M1–M5 built REAL on synthetic data, all §8 gates green (ruff/black/mypy/sqlfluff/pytest 60 +10 integration), branch hawk-eye/database**
- [x] M1 Core stores + encryption: MinIO 4 buckets (versioned, object-lock on models+audit-archive, SSE-S3, 5 least-priv policies, dataset Parquet layout, TF stub) + Postgres schemas via reversible Alembic + least-priv roles + Redis DB0/DB1 — DATABASE-1,2 (Part 23.3/21.5/9.3/8/28.2)
- [x] M2 ClickHouse: 5 tables mirror L0/L6/EDD (BACKEND.md §1/§2/§5) + hot-cold TTL-MOVE tiering + cluster.xml + inverted/skip indices + parameterized search views — DATABASE-3,4 (Part 8/9.2/5.1)
- [x] M3 WORM audit: append-only `hawkeye.audit` topic + audit_event.avsc + WORM writer (hash-chain + daily Merkle) + verify CLI (PASS/FAIL), all six record classes + investigators' actions — DATABASE-5,6 (Part 8/19.2/19.3/9.3)
- [x] M4 Registry: `{layer}/{model}/{version}/` whole-transform-chain serializer + Ed25519 signing + verify-on-load (reject tamper) + access-logging + six-field metadata + Staging→Production→Archived + SoD — DATABASE-7,8 (Part 23.1-23.4/19.2)
- [x] M5 Retention: DPDP/RBI windows + classification-aware + fraud carve-out + hot→cold→archive job + ClickHouse TTL-MOVE; WORM never expired early — DATABASE-9 (Part 28.2/9.3/23.3)
  - Contracts published in CONTEXT.md (newest entry): CH DDLs+partition/TTL, MinIO buckets/registry layout, Redis keyspace, WORM schema+verify CLI, retention windows, encryption+KMS/HSM swap. Local dev py3.9 / pinned runtime py3.12. `ws_DATABASE.json` not in repo → validated against prompt §6 inventory mapping (all 11 components covered).

## 6. 🏗️ PLATFORM (41/41 tasks DONE — see prompts/06_PLATFORM.md) ✅ — branch hawk-eye/platform
- [x] M1 walking skeleton — 26-svc compose (`config` validates), topology + **real degradation switch** (rules-only fallback proven), sizing+compute-placement. `make topology-smoke`/`degradation-demo` pass.
- [x] M2 Terraform (`target=aws|onprem|lightsail`, 24 modules, validates+plans no-creds, AWS security svcs) + migration-map + **ADR-0001 (Lightsail = chosen pilot, documented deviation)** + K8s/Helm (residency labels, conftest 400/400) + zero-trust + mTLS/SPIFFE + mock HSM/TEE/PAM + Vault.
- [x] M3 CI(pyramid+bom-drift+scans+sign) + CD(ArgoCD/blue-green/canary/SLO-rollback) + supply-chain(SBOM/CVE/SAST/secrets) + threat-model + ATLAS map + 7-Sutra map + perf/chaos/**4 SIEM detectors** + vuln-mgmt + VAPT/red-team/model-risk + UAT.
- [x] M4 RTO/RPO + HA configs + immutable backup/restore + **DR drill (rows validated, RTO/RPO report)** + BCP + OTel + golden-signals + SLOs/error-budgets + Alertmanager + incident runbooks + capacity.
- [x] M5 governance DB + governance-api + **24 mocks seeded** + SoD personas + validation sign-off gate + committees + AI-policy/DPIA/DPO/lawful-basis/breach/transparency + **HITL natural-justice gate (alert-only proven)** + vendor-risk + operating-model + **go-live checklist GATE: GO (17/17)**.
- **73 unit/contract tests pass · 26-svc compose validates · all demos green.**

## 7. Cross-laptop blockers / coordination needed
- [!] **[DATA→BACKEND]** EDD label-source-4 (DATA-23) stubbed against `BACKEND.md` §5 — needs real `POST /alerts/{id}/disposition`.
- [x] **[DATA→DATABASE]** ClickHouse events DDL + object-store buckets (`datasets`, `feature-snapshots`) + retention tiering — **RESOLVED by DATABASE-1/3/9**: `events`/`feature_backfill` DDL field-for-field with BACKEND.md §1 (`db/clickhouse/ddl/`), buckets created by `infra/storage/minio/bootstrap_minio.sh`, tiering in `db/retention/`. DATA: swap local fallback → live infra; reconcile when `l0_event` `.avsc`/`.proto` finalized (CONTEXT.md newest entry).
- [x] **[DATA→PLATFORM]** Kafka/Redis/MinIO runtime + schema-registry hosting — **RESOLVED by PLATFORM-1/2** (`make core-up` brings real Kafka/Redis/MinIO/Postgres/ClickHouse/Flink/schema-registry). DATA can swap its in-memory fallbacks. *Open:* topic-name convergence (`hawkeye.*` vs DATA's `events.raw/signals`) — see CONTEXT.md log.
- [~] **[FRONTEND→BACKEND]** Existing route bodies are ALREADY finalised in `backend/openapi.json` (FE: align `[FE-proposed]` types to it; I invented no fields). Genuinely net-new routes FE needs that BACKEND does not yet expose: `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/{status,assign,notes}`, `GET /reports/ews-coverage`, `GET /reports/kris`. FE renders on MSW meanwhile (`VITE_USE_MOCKS`). See CONTEXT.md newest entry.
