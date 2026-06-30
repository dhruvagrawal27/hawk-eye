# TODO.md — Shared Task Board

> Each laptop keeps its own section current (`[ ]` todo, `[~]` in-progress, `[x]` done, `[!]` blocked). Task IDs and the full task lists live in [`BUILD_PLAN.md`](BUILD_PLAN.md) and in each laptop's prompt under `prompts/`. **A task is `[x]` only when its blueprint requirement is validated.** Put cross-laptop blockers in §7.

## 1. 📥 DATA (28 tasks — see prompts/01_DATA.md) — **M1–M5 built, tested & VERIFIED (28/28 tasks, 97/97 tests), branch hawk-eye/data**
- [x] M1 Foundations: L0 schema (+avsc/sample), schema registry, Kafka(topics+clients), Flink(window job), normalizer, Feast+Redis (pure-python fallbacks for infra)
- [x] M2 Simulator + public datasets: 12-typology red-team library (8 fast + 4 slow), ground-truth labels, worked burst, augmentation, 6 dataset loaders
- [x] M3 Source connectors (SCAFFOLD: CBS/payments/IAM-PAM/DLP-DBaudit/HR-IGA/real-telemetry + mock fixtures) + reliability/dedupe/DLQ/count-recon + [x] SWIFT↔CBS recon (REAL)
- [x] M4 Feature engineering catalogue (every 6.1–6.6 + slow-lane) + three-way baselines + DFS + online/offline parity
- [~] M5 Governance/quality/lineage/MDM/retention (REAL); label store: gold=MOCK, EDD source-4 **[!] stubbed — awaits BACKEND `POST /alerts/{id}/disposition`**

## 2. 🤖 ML (29 tasks — see prompts/02_ML.md)
- [ ] M1 L2 unsupervised (IsoForest/ECOD/COPOD/AE) + baselines
- [ ] M2 L3 GBDT (LightGBM/CatBoost/XGBoost) + SHAP + calibration + imbalance
- [ ] M3 L4 sequence (baselines first, then USAD/TranAD/LAXCAT) + honest eval
- [ ] M4 L5 graph (XGB-Graph/GraphSAGE/specialized GNNs) + L6 fusion
- [ ] M5 MLOps (MLflow, champion/challenger, drift), fairness/bias, LLM narrative gateway

## 3. ⚙️ BACKEND (29 tasks — see prompts/03_BACKEND.md) — also owns BACKEND.md
- [ ] M1 FastAPI app, auth/RBAC (Keycloak/JWT), health/metrics
- [ ] M2 L1 rules/BRE + SoD/toxic-combination matrix engine
- [ ] M3 Risk-fusion service + model serving integration + reason codes
- [ ] M4 Alert/case store, EDD feedback loop, PII tokenization + re-id vault
- [ ] M5 EWS/RFA/CRILC/FMR generators + audit-write + narrative gateway route

## 4. 🖥️ FRONTEND (13 tasks — see prompts/04_FRONTEND.md)
- [ ] M1 App shell, SSO/login, routing, API client, RBAC-aware views
- [ ] M2 Triage queue + alert/case detail + entity-360 timeline
- [ ] M3 Explanation panel + graph view + peer comparison
- [ ] M4 Compliance/auditor/model-engineer/admin views + reporting/KRI UI

## 5. 🗄️ DATABASE (9 tasks — see prompts/05_DATABASE.md)
- [ ] M1 ClickHouse (events/history) + hot-cold tiering
- [ ] M2 Postgres (cases/users) + Redis (online features)
- [ ] M3 Object store (MinIO/S3) + model registry layout
- [ ] M4 WORM/immutable audit + retention/archival
- [ ] M5 Encryption-at-rest config + DDL versioning

## 6. 🏗️ PLATFORM (41/41 tasks DONE — see prompts/06_PLATFORM.md) ✅ — branch hawk-eye/platform
- [x] M1 walking skeleton — 26-svc compose (`config` validates), topology + **real degradation switch** (rules-only fallback proven), sizing+compute-placement. `make topology-smoke`/`degradation-demo` pass.
- [x] M2 Terraform (`target=aws|onprem|lightsail`, 24 modules, validates+plans no-creds, AWS security svcs) + migration-map + **ADR-0001 (Lightsail = chosen pilot, documented deviation)** + K8s/Helm (residency labels, conftest 400/400) + zero-trust + mTLS/SPIFFE + mock HSM/TEE/PAM + Vault.
- [x] M3 CI(pyramid+bom-drift+scans+sign) + CD(ArgoCD/blue-green/canary/SLO-rollback) + supply-chain(SBOM/CVE/SAST/secrets) + threat-model + ATLAS map + 7-Sutra map + perf/chaos/**4 SIEM detectors** + vuln-mgmt + VAPT/red-team/model-risk + UAT.
- [x] M4 RTO/RPO + HA configs + immutable backup/restore + **DR drill (rows validated, RTO/RPO report)** + BCP + OTel + golden-signals + SLOs/error-budgets + Alertmanager + incident runbooks + capacity.
- [x] M5 governance DB + governance-api + **24 mocks seeded** + SoD personas + validation sign-off gate + committees + AI-policy/DPIA/DPO/lawful-basis/breach/transparency + **HITL natural-justice gate (alert-only proven)** + vendor-risk + operating-model + **go-live checklist GATE: GO (17/17)**.
- **73 unit/contract tests pass · 26-svc compose validates · all demos green.**

## 7. Cross-laptop blockers / coordination needed
- [!] **[DATA→BACKEND]** EDD label-source-4 (DATA-23) stubbed against `BACKEND.md` §5 — needs real `POST /alerts/{id}/disposition`.
- [!] **[DATA→DATABASE]** ClickHouse events DDL + object-store buckets (`datasets`, `feature-snapshots`) + retention tiering — DATA uses local fallback meanwhile (DATA-5/25).
- [x] **[DATA→PLATFORM]** Kafka/Redis/MinIO runtime + schema-registry hosting — **RESOLVED by PLATFORM-1/2** (`make core-up` brings real Kafka/Redis/MinIO/Postgres/ClickHouse/Flink/schema-registry). DATA can swap its in-memory fallbacks. *Open:* topic-name convergence (`hawkeye.*` vs DATA's `events.raw/signals`) — see CONTEXT.md log.
