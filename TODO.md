# TODO.md — Shared Task Board

> Each laptop keeps its own section current (`[ ]` todo, `[~]` in-progress, `[x]` done, `[!]` blocked). Task IDs and the full task lists live in [`BUILD_PLAN.md`](BUILD_PLAN.md) and in each laptop's prompt under `prompts/`. **A task is `[x]` only when its blueprint requirement is validated.** Put cross-laptop blockers in §7.

## 1. 📥 DATA (28 tasks — see prompts/01_DATA.md) — **M1–M5 built, tested & VERIFIED (28/28 tasks, 97/97 tests), branch hawk-eye/data**
- [x] M1 Foundations: L0 schema (+avsc/sample), schema registry, Kafka(topics+clients), Flink(window job), normalizer, Feast+Redis (pure-python fallbacks for infra)
- [x] M2 Simulator + public datasets: 12-typology red-team library (8 fast + 4 slow), ground-truth labels, worked burst, augmentation, 6 dataset loaders
- [x] M3 Source connectors (SCAFFOLD: CBS/payments/IAM-PAM/DLP-DBaudit/HR-IGA/real-telemetry + mock fixtures) + reliability/dedupe/DLQ/count-recon + [x] SWIFT↔CBS recon (REAL)
- [x] M4 Feature engineering catalogue (every 6.1–6.6 + slow-lane) + three-way baselines + DFS + online/offline parity
- [~] M5 Governance/quality/lineage/MDM/retention (REAL); label store: gold=MOCK, EDD source-4 **[!] stubbed — awaits BACKEND `POST /alerts/{id}/disposition`**

## 2. 🤖 ML (29 tasks — see prompts/02_ML.md) — **branch hawk-eye/ml; foundation + L2-L6 + narrative built & tested (.mlvenv py3.13, 100+ tests green)**
- [x] M1 Foundations (ML-1/2): scaffold/seeds/interfaces, DATA adapters, honest eval (non-PA, temporal/entity splits, leakage guards) + L2 unsupervised (ML-3: IF/ECOD/COPOD/AE/OCSVM via PyOD+torch, ensemble)
- [x] M2a L3 GBDT (ML-4: LightGBM/CatBoost/XGBoost + TreeSHAP + isotonic calibration + imbalance) + strategies (ML-8) + design (ML-9)
- [x] M2b L4 sequence (ML-5: baselines first, then USAD/TranAD/AnomalyTransformer/DeepLog/LAXCAT, non-PA gate) — REAL torch
- [~] M2c L5 graph (ML-6: XGB-Graph default/GraphSAGE/specialized GNNs/GNNExplainer/GADBench ablation) **finishing**; [x] L6 fusion (ML-7: stacked meta + calibration + reason-code assembler → BACKEND §2 alert)
- [x] Narrative gateway (ML-10..13): NEAR AI→Groq→deterministic-template failover (SCAFFOLD providers/attestation), grounding guardrail, audit memo, POST /narratives
- [ ] M3 Pipelines (ML-14..19), M4 MLOps/registry/drift/governance (ML-20..24), M5 fairness (ML-25/26) + robustness (ML-27) + CI suites (ML-28) + phasing/ops (ML-29) — **fanning out next**

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

## 6. 🏗️ PLATFORM (41 tasks — see prompts/06_PLATFORM.md)
- [ ] M1 docker-compose walking skeleton + service map + env/secrets
- [ ] M2 Terraform (AWS ap-south-1 + on-prem) + K8s manifests
- [ ] M3 Security: network/zero-trust, secrets/KMS/HSM(mock), tokenization-egress, TEE-attestation(mock), adversarial-ML/VAPT(mock)
- [ ] M4 Reliability: HA/DR/BCP, observability (Prom/Grafana/OTel), CI/CD, test harness
- [ ] M5 Governance MOCKS (24 items): policies, committees, DPIA, model-risk/validation, fairness program, operating model, go-live checklist

## 7. Cross-laptop blockers / coordination needed
- [!] **[DATA→BACKEND]** EDD label-source-4 (DATA-23) stubbed against `BACKEND.md` §5 — needs real `POST /alerts/{id}/disposition`.
- [!] **[DATA→DATABASE]** ClickHouse events DDL + object-store buckets (`datasets`, `feature-snapshots`) + retention tiering — DATA uses local fallback meanwhile (DATA-5/25).
- [!] **[DATA→PLATFORM]** Kafka/Redis/MinIO runtime (PLATFORM-1 docker-compose) + schema-registry hosting — DATA uses InProcessBus/in-memory fallback.
