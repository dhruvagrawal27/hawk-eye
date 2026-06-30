# TODO.md — Shared Task Board

> Each laptop keeps its own section current (`[ ]` todo, `[~]` in-progress, `[x]` done, `[!]` blocked). Task IDs and the full task lists live in [`BUILD_PLAN.md`](BUILD_PLAN.md) and in each laptop's prompt under `prompts/`. **A task is `[x]` only when its blueprint requirement is validated.** Put cross-laptop blockers in §7.

## 1. 📥 DATA (28 tasks — see prompts/01_DATA.md)
- [ ] M1 Foundations: L0 schema, schema registry, Kafka, Flink, normalizer, Feast+Redis
- [ ] M2 Simulator + public datasets (red-team typology library, labels, augmentation, loaders)
- [ ] M3 Source connectors (SCAFFOLD) + reliable ingestion + SWIFT↔CBS recon
- [ ] M4 Feature engineering catalogue + feature store materialization
- [ ] M5 Data governance / quality / lineage / label store

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

## 6. 🏗️ PLATFORM (41 tasks — see prompts/06_PLATFORM.md)
- [ ] M1 docker-compose walking skeleton + service map + env/secrets
- [ ] M2 Terraform (AWS ap-south-1 + on-prem) + K8s manifests
- [ ] M3 Security: network/zero-trust, secrets/KMS/HSM(mock), tokenization-egress, TEE-attestation(mock), adversarial-ML/VAPT(mock)
- [ ] M4 Reliability: HA/DR/BCP, observability (Prom/Grafana/OTel), CI/CD, test harness
- [ ] M5 Governance MOCKS (24 items): policies, committees, DPIA, model-risk/validation, fairness program, operating model, go-live checklist

## 7. Cross-laptop blockers / coordination needed
- [ ] (none yet — add here, tag the owning laptop, and mirror in CONTEXT.md)
