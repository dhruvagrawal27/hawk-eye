# Hawk-Eye — Build Plan

> Real-time Insider & Privileged-User Fraud Detection. This plan decomposes the [implementation blueprint](Insider_Fraud_Detection_Implementation_Blueprint%20(2).md) (34 parts, 380 audited tasks) into **6 workstreams → 149 ordered build tasks**. Built local-first on synthetic data; nothing here needs a real bank system to run.

## Status legend

| Status | Meaning |
|---|---|
| **REAL** | Works as real code on synthetic/mock data, locally |
| **SCAFFOLD** | Code written & correct, but goes live only with a real external resource (bank feed, cloud creds, API key, HSM/TEE hardware, human validator) |
| **MOCK** | Hardcoded/simulated stand-in for a human/legal/hardware act (seeded records, generated governance docs, fake attestation service) — demonstrates the workflow, not the real act |

**Totals:** 112 REAL · 20 SCAFFOLD · 17 MOCK

## Workstreams at a glance

| # | Workstream | Tasks | Milestones | REAL / SCAFFOLD / MOCK |
|---|---|---|---|---|
| 1 | 📥 **DATA** | 28 | 5 | 23 / 4 / 1 |
| 2 | 🤖 **ML** | 29 | 5 | 26 / 2 / 1 |
| 3 | ⚙️ **BACKEND** | 29 | 5 | 25 / 4 / 0 |
| 4 | 🖥️ **FRONTEND** | 13 | 4 | 13 / 0 / 0 |
| 5 | 🗄️ **DATABASE** | 9 | 5 | 9 / 0 / 0 |
| 6 | 🏗️ **PLATFORM** | 41 | 5 | 16 / 10 / 15 |

## Recommended build order (vertical slice first)

Build a thin end-to-end slice before deepening any single workstream, so a synthetic fraud burst becomes a scored alert in the UI as early as possible:

1. **Slice 0 — Walking skeleton:** PLATFORM docker-compose (Kafka/Redis/Postgres/ClickHouse) → DATA L0 schema + simulator → BACKEND L1 rules → ML L2 anomaly + L6 fusion → BACKEND alerts API → FRONTEND triage queue.
2. **Deepen DATA:** full feature catalogue + Feast/Redis + connectors (mock).
3. **Deepen ML:** L3 GBDT+SHAP → L4 sequence → L5 graph → MLOps/feedback loop.
4. **Deepen FRONTEND/BACKEND:** entity-360, explanation panel, graph view, EDD loop, RBAC, reporting.
5. **DATABASE + PLATFORM hardening:** WORM audit, retention, security, HA/DR, governance mocks, CI/CD.

---

## 📥 DATA — Workstream

This workstream delivers the data backbone of hawk-eye: the L0 unified actor-action-object event schema, the Kafka/Flink/Feast+Redis/ClickHouse streaming-and-feature substrate, a fully synthetic agent-based simulator that emits labelled insider-fraud telemetry, scaffolded source connectors for CBS/SWIFT/IAM/PAM/DB-audit/HR, the full feature-engineering catalog feeding L2-L5, dataset/label sourcing (public benchmarks plus weak/synthetic/EDD labels), and data governance/quality/lineage. Everything is REAL on synthetic and public data; only live-bank feeds and real fraud-label sources are scaffolded or mocked.

**Tech:** Apache Kafka (Redpanda alt), Apache Flink (stateful streaming + CEP), Feast + Redis online store, ClickHouse, MinIO/S3 + Parquet, SimPy/Mesa agent simulator, SDV (CTGAN/TVAE/diffusion), featuretools (Deep Feature Synthesis), Snorkel (weak labels), Great Expectations / Pandera, Avro/Protobuf + schema registry, DVC/MLflow lineage, Python (pandas/pyarrow)

### M1 Foundations — Schema & Streaming Substrate
*Stand up the canonical L0 event model and the Kafka/Flink/Feast+Redis/ClickHouse spine so every downstream layer reads one normalized event stream.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATA-1 | L0 Unified Event Model (canonical actor-action-object schema) | schemas/l0_event.py + l0_event.avsc/.proto with Actor/Action/Object/Context/Linkage field groups; sample event_id/ts/actor/action/object/context payload | REAL | — | M |
| DATA-2 | Schema registry, versioning & evolution governance | registry/schema_registry config + compatibility (backward/forward) policy and event-schema-governance rules | REAL | DATA-1 | S |
| DATA-3 | Kafka ingestion cluster + topic topology | infra/kafka/ topic definitions (events, alerts, audit) and producer/consumer clients (Redpanda-compatible) | REAL | PLATFORM-1 | M |
| DATA-4 | Flink stateful stream processor scaffold (keyed state, windows, CEP) | streaming/flink_jobs/ base job with checkpointing and keyed per-entity state | REAL | DATA-3 | M |
| DATA-5 | Normalization/ingest layer landing events into Kafka (hot) + ClickHouse (history) | ingest/normalizer.py mapping raw source rows to L0 events; ClickHouse events table DDL + sink | REAL | DATA-1, DATA-3, PLATFORM-1 | M |
| DATA-6 | Feast + Redis online feature store (single train/serve definition) | feature_store/feature_repo (Feast) + Redis online store config | REAL | PLATFORM-1 | M |

### M2 Synthetic Simulator & Public Datasets
*Produce realistic labelled telemetry with known ground truth (the project's only real training signal) and wire in public benchmark datasets, so all downstream layers have data without any live-bank dependency.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATA-7 | Agent-based synthetic simulator core (SimPy/Mesa harness) | sim/simulator.py emitting labelled Parquet + Kafka stream in the L0 schema | REAL | DATA-1, DATA-3 | L |
| DATA-8 | Population + normal-behaviour models | sim/population.py (N employees: role/dept/branch/tenure/manager/peer_group/privileged_flag) + sim/normal_behaviour.py (per-role diurnal/weekly activity generators) | REAL | DATA-7 | M |
| DATA-9 | Fraud-scenario injectors + red-team typology library | sim/scenarios/ one module per typology (beneficiary-then-approve, dormant takeover, SWIFT-without-CBS, suspense/nostro lapping, privilege self-grant, bulk exfil before resignation, maker-checker collusion ring, rogue-trader) | REAL | DATA-8 | L |
| DATA-10 | Ground-truth labelling + scale knobs + worked end-to-end scenario | sim/labels.py tagging is_fraud/scenario_id/actor_id/ring_id; scale config (agents, ~18mo span, 0.1-1% fraud rate); replayable create_beneficiary->approve_payment burst scenario | REAL | DATA-9 | M |
| DATA-11 | Generative tabular augmentation (rare-class only) | sim/augment.py using SDV CTGAN/TVAE/diffusion in feature space, anchored to real distributions, with imbalance handling hooks | REAL | DATA-10 | M |
| DATA-12 | Public/benchmark dataset loaders + references | datasets/loaders/ for CMU-SEI CERT (r4.2/r5.2/r6.2), IEEE-CIS, ULB Credit-Card, PaySim, Elliptic, SPEDIA/Amazon-FDB mapped to L0 | REAL | DATA-1 | M |

### M3 Source Connectors (mock/scaffold) & Reliable Ingestion
*Provide the production-shaped connector surface for all bank source systems as scaffolds plus reliable ingestion patterns, swapping the simulator stream for real feeds when credentials exist.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATA-13 | Transaction-source connectors: CBS/SWIFT/RTGS/NEFT/IMPS/UPI, GL/suspense/nostro, treasury blotter | connectors/cbs/, connectors/payments/ adapters (Finacle/Flexcube/BaNCS/T24 shapes) reading mock fixtures into L0 | SCAFFOLD | DATA-5 | L |
| DATA-14 | Identity/access + data-layer + change/HR connectors | connectors/iam_pam/ (IAM/AD, CyberArk/BeyondTrust, VPN), connectors/dlp_dbaudit/, connectors/hr_iga/ (joiner-mover-leaver, entitlement) reading mock fixtures into L0 | SCAFFOLD | DATA-5 | L |
| DATA-15 | Unified ingestion-adapter framework + CDC/batch pattern + collectors | connectors/base_adapter.py, CDC->Kafka streaming + periodic-batch (slow-lane) ingestion pattern, read-only collector agents | SCAFFOLD | DATA-13, DATA-14 | M |
| DATA-16 | SWIFT<->CBS reconciliation join (the PNB control) | ingest/recon/swift_cbs_join.py producing reconciliation-mismatch signals | REAL | DATA-13 | M |
| DATA-17 | Ingestion reliability + feed-loss reconciliation + source-onboarding playbook | ingest/reliability (idempotent dedupe-by-event_id, DLQ, backpressure hooks), ingested-count vs source reconciliation, docs/source_onboarding_playbook.md (discovery->mapping->connector->DQ->backfill->lineage->shadow->promote) | REAL | DATA-15 | M |
| DATA-18 | Real-telemetry ingestion + label sourcing scaffold | connectors/real_telemetry/ scaffold mapping CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR to L0 with gold-historical / weak / EDD label hooks (awaits live feeds + real labels) | SCAFFOLD | DATA-15, DATA-23 | M |

### M4 Feature Engineering & Feature Store
*Compute the full insider-fraud feature catalog (identity, transaction, data-layer, change/HR, graph, temporal) over the three-way baselines, served online via Feast/Redis and backfilled offline in ClickHouse with no train/serve skew.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATA-19 | Three-way baseline framework (per-entity, per-peer-group, global) with time decay | features/baselines.py computing decayed baselines; Redis caching of per-entity + peer-group stats with TTL and scheduled recompute | REAL | DATA-4, DATA-6 | M |
| DATA-20 | Identity/access + transaction feature families | features/identity_access.py (off-hours, login velocity, impossible-travel, dormant reactivation, privilege-escalation velocity, session/concurrency anomaly, no-leave streak) + features/transaction.py (amount z-score, just-under-threshold, velocity, new-beneficiary->high-value latency, maker-checker pairing, reversal clustering, overrides, suspense aging, SWIFT<->CBS mismatch, SI/beneficiary modification) | REAL | DATA-19 | L |
| DATA-21 | Data-layer + change/HR + graph + temporal feature families | features/data_layer.py (export volume/bulk-export flag, DB-write-without-app-txn, sensitive/PAN access, log-tamper proxy, orphaned-account use), features/change_hr.py (self-grant, short-lived grants, leaver-window, referrer-cluster, toxic-combination flags), features/graph.py (degree/centrality, shared device/IP/phone, circular-flow/mule motifs, collusion subgraphs, employee<->customer linkage for L5), features/temporal.py (drift vs rolling baseline, change-point, session-sequence, periodicity breaks for L4) | REAL | DATA-19 | L |
| DATA-22 | Streaming compute, online serving, offline backfill, automated feature generation | Flink jobs computing sliding/tumbling windowed features (keyed per-entity); Feast/Redis online serving; ClickHouse offline backfill with identical feature defs (skew avoidance); featuretools DFS auto-generation module | REAL | DATA-20, DATA-21, DATA-6 | L |

### M5 Labels, Datasets, Governance, Quality & Lineage
*Source labels from all four channels, version/split datasets without leakage, and enforce catalog/classification/quality/lineage/MDM so models train on governed, auditable data.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATA-23 | Label sourcing: gold cases (mock), weak labels, synthetic injection, EDD feedback | labels/label_store.py + label-source-1 gold historical Vigilance/CBI cases (mock fixtures), label-source-2 Snorkel rule-hit weak labels, label-source-3 synthetic red-team positives (from DATA-10), label-source-4 EDD-disposition ingestion endpoint | MOCK | DATA-10, BACKEND-EDD-DISPOSITION-API | M |
| DATA-24 | Splits & leakage avoidance | datasets/splits.py with temporal split, entity-disjoint validation, leaky-feature removal | REAL | DATA-12, DATA-22, DATA-23 | M |
| DATA-25 | Dataset storage, versioning & lineage | ClickHouse + MinIO/S3 partitioned Parquet; DVC/MLflow curated-set versioning + content hash; Feast offline store; end-to-end lineage (source->feature->model->alert) with dataset hash + feature-set version per model | REAL | DATA-24, DATABASE-RETENTION-TIERING | M |
| DATA-26 | Data catalog, dictionary, classification & MDM/entity resolution | governance/catalog (every L0 field documented/owned), classification tags (PII/PAN/sensitive vs operational) driving masking/access/retention, mdm/entity_resolution.py (one employee/customer across CBS/HR/IAM) | REAL | DATA-1, DATA-25 | M |
| DATA-27 | Data quality + validation tests + retention/minimization governance | quality/expectations (Great Expectations/Pandera: completeness, validity, freshness, schema conformance, range/null, distribution), DQ SLAs + dashboards, purpose-bound retention/erasure lifecycle with fraud carve-outs | REAL | DATA-26 | M |
| DATA-28 | Phase-0 foundations integration milestone | End-to-end Phase-0 wiring: Kafka + ClickHouse + L0 model live, synthetic transactions + IAM/PAM ingested, simulator red-team library streaming, shadow-mode-ready data path for L1 BRE | REAL | DATA-5, DATA-9, DATA-22 | M |

**Cross-workstream dependencies:**
- PLATFORM-* must provision the Kafka/Flink/Redis/ClickHouse/MinIO runtime (on-prem or AWS MSK/Managed-Flink/ElastiCache/EC2) before DATA streaming infra can run
- BACKEND L1 rules/SoD engine consumes the L0 event stream and the Redis online features produced here
- ML (L2-L6) consumes DATA features, datasets, splits and labels; ML training DAGs and transfer-learning depend on DATA feature tables and the label store
- DATABASE owns WORM/append-only retention tiering and ClickHouse hot-cold storage that DATA governance/lineage write into
- FRONTEND/BACKEND EDD disposition API feeds DATA label-source-4 (EDD feedback loop)
- ML drift monitors and model registry consume DATA lineage (dataset hash + feature-set version per model)

---

## 🤖 ML — Workstream

Delivers the full multi-layer detection model stack (L2 unsupervised, L3 GBDT+SHAP, L4 sequence, L5 graph, L6 fusion/calibration) plus honest non-point-adjusted evaluation, training/retraining pipelines, MLflow champion-challenger MLOps, drift monitoring, fairness/bias testing, adversarial robustness, and a TEE-attested LLM narrative gateway with deterministic fallback. Nearly all components are buildable on synthetic/CERT/Elliptic data; only the live NEAR AI / Groq TEE provider calls and attestation verification are scaffolded, and the independent model-validation sign-off is mocked.

**Tech:** scikit-learn, PyOD, XGBoost, LightGBM, CatBoost, PyTorch, PyTorch Geometric, SHAP, featuretools, MLflow, Airflow/Dagster, Evidently, Prometheus/Grafana, Fairlearn, Jinja2, NEAR AI Cloud + Groq (OpenAI-compatible)

### M1 Foundations: ML stack, evaluation harness, and individual detectors
*Stand up the Python ML stack and an honest leakage-safe evaluation harness, then implement every layer's individual detector/model in isolation against synthetic and CERT/Elliptic data.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| ML-1 | Python ML stack + project scaffold | ml/ package with pinned deps (scikit-learn, XGBoost/LightGBM/CatBoost, PyTorch, PyOD, PyG, featuretools, SHAP), fixed-seed config, BaseDetector interface | REAL | — | S |
| ML-2 | Honest evaluation + metrics module (non-point-adjusted, leakage-safe) | ml/eval/metrics.py: PR-AUC/AP, precision@k, alert-to-true-fraud ratio, range/affiliation-aware PR, VUS-PR, time-based splits, leakage/temporal-CV guards | REAL | ML-1 | L |
| ML-3 | L2 unsupervised detectors (IF, Autoencoder, ECOD/COPOD, One-Class SVM) + ensemble fusion | ml/layers/l2/: detector classes with default params (IF n_est=150/max_samples=256, AE bottleneck/dropout, param-free ECOD/COPOD), per-feature explanations, 2-3 detector score fusion | REAL | ML-1, ML-2, DATA-1 | L |
| ML-4 | L3 GBDT scorers (LightGBM/CatBoost/XGBoost) + benchmark harness + TreeSHAP | ml/layers/l3/: three scorers, three-way metric+latency benchmark selector, imbalance handling (1:3-1:10 subsampling, class weights/focal loss), isotonic/Platt calibration, live TreeSHAP reason codes | REAL | ML-1, ML-2, DATA-1 | L |
| ML-5 | L4 sequence models (simple baselines + USAD/TranAD/Anomaly-Transformer/DeepLog/LAXCAT) | ml/layers/l4/: windowed PCA/IF + matrix-profile baselines first, then USAD, TranAD, LSTM-AE/Deep-IF/Anomaly-Transformer, DeepLog/LogAnomaly, supervised LAXCAT session explainer | REAL | ML-1, ML-2, DATA-1 | L |
| ML-6 | L5 graph construction + models (XGB-Graph, GraphSAGE, camouflage-resistant GNNs) + GNNExplainer | ml/layers/l5/: typed entity-edge graph build/incremental refresh, k-hop-feature XGB-Graph, GraphSAGE, CARE-GNN/PC-GNN/BWGNN/GAT/HGT, GNNExplainer attribution, GADBench 0->2-hop ablation harness | REAL | ML-1, ML-2, DATA-1 | L |

### M2 Fusion, learning strategies, and the narrative gateway
*Combine per-layer scores into a calibrated 0-100 risk score with assembled reason codes, add the imbalance/PU/transfer-learning strategies that the layers share, and build the LLM narrative gateway with failover and TEE attestation.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| ML-7 | L6 stacked fusion + calibration + reason-code assembler | ml/layers/l6/: logistic/shallow-LightGBM meta-model over per-layer scores + rule hits, calibration to 0-100 with severity x confidence, reason-code assembler (rule provenance + SHAP top features + attention/graph evidence) | REAL | ML-3, ML-4, ML-5 | L |
| ML-8 | Shared learning strategies: imbalance, PU/semi-supervised, transfer-learning pretrain | ml/strategies/: negative subsampling + class-weight/focal-loss + post-hoc calibration utilities, PU/semi-supervised learners on unlabeled majority, CERT/Elliptic encoder pretrain + fine-tune for L4/L5 | REAL | ML-4, ML-5, DATA-2 | M |
| ML-9 | Peer-fair / alert-only scoring design + 'simple-beats-deep' decision summary | ml/design/: peer-relative scoring layer, zero-inline-blocking contract, per-layer L1-L6 reference table and one-screen layer->default-model mapping | REAL | ML-7 | S |
| ML-10 | Narrative gateway orchestration: narrate() with failover + deterministic Jinja fallback | ml/narrative/gateway.py: narrate() primary->secondary->template failover, Jinja template rendering structured narrative from reason codes (always works, no LLM) | REAL | ML-7 | M |
| ML-11 | LLM provider calls: NEAR AI primary + Groq secondary | ml/narrative/providers/: NEAR AI Cloud client (cloud-api.near.ai/v1, openai/gpt-oss-120b, gateway mode) and Groq client (api.groq.com/openai/v1), env-keyed, retry/timeout | SCAFFOLD | ML-10, PLATFORM-1 | M |
| ML-12 | TEE attestation verify+store and audit memo writer + narrative guardrails | ml/narrative/attestation.py verify_and_store_attestation() (Intel TDX + NVIDIA dual-quote verify) plus audit memo writer (provider, tee_attested, attestation_id, model, prompt_hash, ts) and anti-fabrication/de-anon grounding guardrails | SCAFFOLD | ML-11, DATABASE-1 | M |
| ML-13 | POST /narratives/{alert_id} endpoint (TEE LLM narrative) | ml/narrative/api.py route wiring narrate() + attestation + audit memo to the alert id | REAL | ML-10, ML-12, BACKEND-1 | S |

### M3 Training, retraining, and inference pipelines
*Wrap every layer in reproducible, layer-parameterized training DAGs, build the EDD feedback retraining loop and active learning, and orchestrate fast-lane and async/batch inference cadences.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| ML-14 | Layer-parameterized training DAG (pull -> features -> train -> validate -> calibrate -> register) | pipelines/train_dag.py (Airflow/Dagster) generic per-layer DAG pulling labeled+unlabeled features from ClickHouse/Feast | REAL | ML-2, DATA-1, PLATFORM-1 | L |
| ML-15 | Per-layer training implementations (L2 unsupervised, L3 time-aware GBDT, L4 sequence, L5 graph, L6 fusion) | pipelines/train/l2..l6.py: normal-window fits, time-aware CV + early stopping + scale_pos_weight, windowed baselines-first sequence training, graph refresh+train, stacked meta-learner training | REAL | ML-14, ML-3, ML-4, ML-5, ML-6, ML-7 | L |
| ML-16 | EDD feedback loop + active-learning retraining | pipelines/feedback.py: alert -> investigator disposition -> labeled store -> uncertainty-prioritized active learning -> scheduled retrain | REAL | ML-15, DATABASE-1 | M |
| ML-17 | Reproducibility & governance artifacts (seeds, dataset/feature hashes, MLflow tracking) | pipelines/repro.py: fixed seeds, recorded dataset+feature hashes, full MLflow run logging, persist exact feature vector + model version with every score | REAL | ML-14, PLATFORM-1 | M |
| ML-18 | Inference orchestration: fast-lane sync + async L4/L5 + batch cadences | pipelines/inference/: sync L2/L3 path, async L4 sequence + L5 graph on session-close/batch, Airflow/Dagster schedules (L4 15min-hourly, L5 hourly-daily, slow-lane daily) | REAL | ML-15, BACKEND-1 | M |
| ML-19 | Backtesting/replay harness | pipelines/backtest.py: stream historical ClickHouse events through candidate models to estimate detection + alert volume | REAL | ML-15, ML-2, DATA-1 | M |

### M4 MLOps: registry, drift, champion-challenger, and governance
*Operationalize the models with MLflow registry/versioning, champion-challenger with shadow/canary and signed-load CD, drift detection and drift-triggered retraining, and the model-governance/MRM artifact set.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| ML-20 | MLflow registry & versioning (training-data hash, features, metrics, approving reviewer) | mlops/registry.py + champion/challenger registry conventions, model inventory (every L2-L6 + LLM gateway model with owner/purpose/risk-tier/version) | REAL | ML-17, PLATFORM-1 | M |
| ML-21 | Champion/challenger + shadow + canary + signed-load CD with auto-rollback | mlops/promotion.py: shadow scoring (challengers score live traffic, no alerts), canary promotion, signature verification on model load, automatic rollback on metric regression | REAL | ML-20, ML-18 | L |
| ML-22 | Drift detection + drift-triggered retraining + threshold/alert-volume governance | mlops/drift.py: PSI/KS data drift + rolling precision/recall concept drift via Evidently, Prometheus/Grafana degradation alerts, threshold tuning to analyst throughput (precision@k, alert-to-true ratio), drift-crossing retrain trigger | REAL | ML-21, ML-16 | M |
| ML-23 | Model governance & MRM artifacts (cards, tiering, change/approval workflow, monitoring) | mlops/governance/: per-model model cards (intended use, data+hash, features, metrics, limitations), risk tiering, change->validation->approval->deploy workflow, ongoing monitoring vs realized fraud, ML-specific validation scope notes | REAL | ML-20 | M |
| ML-24 | Independent model-validation report + bias/fairness sign-off (simulated) | mlops/governance/validation_report.py: model-risk validation report (data quality, assumptions, performance/stability, limitations) wrapping real fairness metrics, with simulated independent-reviewer sign-off seeded against the model version | MOCK | ML-23, ML-26 | S |

### M5 Trustworthiness: fairness, robustness, and CI test suites
*Add disparate-impact/fairness testing and mitigations, adversarial-robustness and poisoning/inversion defenses, and the behavioral/metamorphic/regression/fairness CI test suites that gate deployment.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| ML-25 | Disparate-impact + fairness metrics across employee attributes | fairness/metrics.py: demographic-parity difference, equal-opportunity/equalized-odds gaps, disparate-impact ratio across grade/seniority/age/gender/region/department | REAL | ML-7, ML-2 | M |
| ML-26 | Fairness mitigations + feedback-loop fairness trap monitoring + explainability-as-right | fairness/mitigations.py: peer-group-relative scoring, pre/in/post-processing techniques, no-proxy enforcement, label-distribution monitoring for disproportionate confirmation, reason-codes+narrative on every alert | REAL | ML-25, ML-9, ML-22 | M |
| ML-27 | Adversarial robustness, evasion mitigations, poisoning + inversion/inference defenses + explanation-manipulation defenses | robustness/: adversarial detector testing, peer-relative/hidden-threshold/randomized-sampling/diverse-ensemble evasion mitigations, train-set anomaly+change-point+label-distribution poisoning checks, rate-limited authenticated internal-only inference API + no raw-score exposure, interpretable-component preference over post-hoc | REAL | ML-7, ML-16 | L |
| ML-28 | ML CI test suites: behavioral, metamorphic/invariance, directional, regression, drift, fairness-gated | tests/ml/: known-fraud-high/known-benign-low behavioral tests on red-team library, amount-scaling/irrelevant-field invariance, off-hours+new-beneficiary+high-value directional monotonicity, fixed-eval-set regression, prod drift/data-integrity checks, fairness gated in CI | REAL | ML-25, ML-7, DATA-2 | L |
| ML-29 | Phased rollout mapping + operational/business metrics | docs/phasing.md + metrics/ops.py: Phase 1 (L2 baselines) -> Phase 2 (L3+SHAP) -> Phase 3 (L4/L5 slow-lane) -> Phase 4 (active-learning + red-team), plus alert-volume-vs-capacity, MTTD, FPR, RBI <=30-day TAT compliance metrics | REAL | ML-22, ML-28 | S |

**Cross-workstream dependencies:**
- DATA-* feature store (ClickHouse + Feast) supplies labeled+unlabeled training features and online feature vectors for all layers L2-L6 (training and inference)
- DATA-* synthetic + CERT/Elliptic data and red-team typology library used for transfer-learning pretrain, behavioral/metamorphic tests, and backtesting replay
- DATABASE-* labeled disposition store and persistence schemas for model registry, attestation, audit memos, and per-score feature/version provenance
- BACKEND-* scoring/orchestration service that invokes layer models and the narrate() gateway, surfaces reason codes + alerts, and exposes the rate-limited internal inference API
- PLATFORM-* hosts MLflow server, Airflow/Dagster scheduler, Prometheus/Grafana, and provisions TEE secrets (NEAR_AI_API_KEY / GROQ_API_KEY)

---

## ⚙️ BACKEND — Workstream

The backend workstream delivers the FastAPI control plane plus the Rust hot-path service tier for the insider-fraud system: Keycloak OIDC auth with short-lived JWTs, an RBAC permission matrix (8 roles x 9 capabilities) with SoD enforcement, the full /api/v1 surface (alerts, entities, explanations, rules, models, audit, admin, regulatory exports), the L1 rules/BRE plus SoD toxic-combination engine, the online inference and L6 risk-fusion path (ONNX/Triton served via a Rust scoring gateway), PII tokenization with a re-identification vault, the EDD disposition/feedback write path, and the slow-lane EWS/CRILC/FMR regulatory generators. It is the integration spine the ML models, frontend, and databases all bind to.

**Tech:** FastAPI/Uvicorn, Pydantic, Keycloak (OIDC/OAuth2, JWT), OPA, Rust (axum/actix, ort/candle), ONNX Runtime / Triton, Kafka, Flink CEP, Redis/Feast, ClickHouse, PostgreSQL, HashiCorp Vault, HMAC-SHA256, TreeSHAP, Kong/APISIX gateway, Prometheus / mTLS

### M1 API Foundations & Identity
*Stand up the FastAPI app, transport/observability baseline, Keycloak-backed auth, RBAC/SoD enforcement, and the canonical API and payload contracts everything else binds to.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| BACKEND-1 | FastAPI app skeleton, transport & observability baseline | services/api/app/main.py with /api/v1 base path, JSON-over-HTTPS, mTLS-internal config, GET /health and GET /metrics (Prometheus), settings/config module | REAL | — | M |
| BACKEND-2 | Keycloak OIDC auth + short-lived JWT issuance/refresh | app/auth/oidc.py + routes auth_routes.py (POST /auth/login, POST /auth/refresh) doing OIDC token exchange/refresh and JWT validation middleware | REAL | BACKEND-1, PLATFORM-KEYCLOAK | M |
| BACKEND-3 | RBAC permission matrix + SoD enforcement engine | app/auth/rbac.py encoding 8 roles x 9 capabilities enforced per API call, OPA policy bundle, plus SoD rules (deployer cannot label/close own alerts; investigator cannot tune rules generating their alerts) | REAL | BACKEND-2 | M |
| BACKEND-4 | Canonical API & payload contracts (OpenAPI + schemas) | app/schemas/*.py Pydantic models for the sample alert schema (alert_id, entity_id, risk_score, severity, confidence, status, contributing_layers, reason_codes, exposure_inr, sla_due_ts, pii_tokenized) and the disposition request/response contract; generated OpenAPI spec | REAL | BACKEND-1 | M |

### M2 L1 Rules / BRE & SoD Matrix Engine
*Build the deterministic detection baseline: the rules/BRE engine, the SoD toxic-combination scoring engine, privileged-session/entitlement-change rule logic, and change-controlled rule management.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| BACKEND-5 | L1 Rules / Business Rules Engine (deterministic thresholds) | rules_engine/ module (Drools-style or Flink-CEP + Python evaluator) implementing the deterministic threshold baseline as a necessary-but-insufficient Layer 1 | REAL | BACKEND-4, DATA-FEATURES | L |
| BACKEND-6 | SoD / toxic-combination matrix scoring engine | rules_engine/sod_matrix.py scoring events against the bank SoD matrix, with OPA for entitlement logic; emits toxic-combination flags | REAL | BACKEND-5 | L |
| BACKEND-7 | Privileged-session & entitlement-change rule logic | rules_engine/privileged.py: privileged-session correlation, DB-write-without-app-transaction detection, entitlement-change/self-grant monitoring, least-privilege checks | REAL | BACKEND-6, DATA-FEATURES | M |
| BACKEND-8 | Change-controlled rule/threshold CRUD with four-eyes approval | rules_routes.py (GET/POST/PUT /rules, Compliance role) with four-eyes approval workflow and audit on every rule/threshold change | REAL | BACKEND-5, BACKEND-3, DATABASE-AUDIT | M |

### M3 Online Inference, Risk Fusion & Model Serving
*Wire the real-time scoring path: ONNX/Triton model serving, the Rust hot-path gateways, the L1 short-circuit, the L6 fusion service with reason codes, idempotency, graceful degradation, and registry-driven hot-swap.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| BACKEND-9 | Model-serving layer (ONNX Runtime / Triton) | serving/ ONNX Runtime + Triton deployment scoring L2 unsupervised + L3 GBDT (+L4 session) inline, model-version recorded on every score | REAL | BACKEND-4, ML-EXPORT-ONNX | L |
| BACKEND-10 | Rust hot-path service tier (ingest/enrichment + rules/scoring + inference gateway) | gateway/ Rust crates: ingestion/enrichment gateway, rules/scoring gateway, and online inference service via ort/candle | REAL | BACKEND-5, BACKEND-9, DATA-KAFKA, DATA-FEAST | L |
| BACKEND-11 | L1 rules gateway hard-hit short-circuit | gateway/l1_shortcircuit.rs emitting HIGH alert immediately on hard rule hit within the online path | REAL | BACKEND-10, BACKEND-6 | S |
| BACKEND-12 | L6 risk-fusion service with inline reason codes | fusion/service.py producing calibrated 0-100 score + severity x confidence + reason codes via inline (non-interaction) TreeSHAP, plus rule-provenance/attention assembly | REAL | BACKEND-9, ML-L6-FUSION | L |
| BACKEND-13 | End-to-end online inference topology wiring | Compose/k8s wiring Kafka(events) -> Flink enrich+window -> Redis/Feast -> L1 gateway -> model-serving -> L6 fusion -> Kafka(alerts)/ClickHouse/feature-snapshot | REAL | BACKEND-10, BACKEND-11, BACKEND-12, DATA-FLINK, DATABASE-CLICKHOUSE | M |
| BACKEND-14 | Idempotency, exactly-once & reliability patterns | Deterministic event_id keying, Flink checkpointing + Kafka transactions, dedupe, retries-with-backoff, dead-letter queues, circuit breakers, bulkheads, backpressure | REAL | BACKEND-13 | M |
| BACKEND-15 | Graceful degradation to L1-rules-only fallback | gateway degradation logic: when model server unavailable fall back to L1 rules only and mark events for re-scoring | REAL | BACKEND-13 | S |
| BACKEND-16 | Registry-driven artifact load + signature verify + canary hot-swap | serving/loader: pull Production artifact, verify signature, canary hot-swap, record model version per score | REAL | BACKEND-9, ML-REGISTRY | M |

### M4 API Surface, PII Tokenization & EDD Feedback
*Expose the full investigator/admin API surface, the PII tokenization + re-identification vault, the human-in-the-loop disposition/feedback write path, and the audit/governance routes.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| BACKEND-17 | PII tokenization layer + local re-identification vault | app/pii/tokenizer.py deterministic keyed HMAC-SHA256 tokens (EMP-7f3a, ACCT-4d22) running before egress, with token<->real mapping in a local vault and audited de-tokenization for authorized users | REAL | BACKEND-3, PLATFORM-VAULT, DATABASE-PG | M |
| BACKEND-18 | Field-level PII encryption + at-rest/in-transit protection | app/pii/crypto.py field-level encryption/tokenization/masking of PII/PAN, mTLS in transit, at-rest encryption wired to KMS/HSM keys | REAL | BACKEND-17, PLATFORM-HSM | M |
| BACKEND-19 | Alert routes + queue + entity-360 + explanations | alert_routes.py (GET /alerts paginated/filtered, GET /alerts/{id}), entity_routes.py (GET /entities/{id}, /timeline, /graph, /peers), GET /explanations/{alert_id} returning SHAP + rule provenance + attention | REAL | BACKEND-4, BACKEND-3, BACKEND-12, DATABASE-CLICKHOUSE | L |
| BACKEND-20 | EDD disposition + feedback write path (human-in-the-loop, alert-only) | POST /alerts/{id}/assign, POST /alerts/{id}/disposition (writes label, audit_id, queues for retraining), POST /feedback, POST /alerts/{id}/block-request; enforces mandatory human decision before any classification and never auto-classifies | REAL | BACKEND-19, DATABASE-AUDIT, ML-FEEDBACK-LOOP | M |
| BACKEND-21 | Model, drift & metrics routes (registry-driven) | model_routes.py: GET /models, POST /models/{id}/promote, GET /drift, GET /metrics/model | REAL | BACKEND-16, ML-REGISTRY, ML-DRIFT | M |
| BACKEND-22 | Audit, admin & RBAC-scoped case access | GET /audit (immutable trail incl. who-viewed-whom, Auditor role), admin_routes.py (GET/POST /admin/users), dashboard RBAC need-to-know (analysts see only assigned cases), session controls, watch-the-watchers fairness logging | REAL | BACKEND-3, DATABASE-AUDIT | M |
| BACKEND-23 | Severity-based escalation routing + SLA/TAT timers | app/workflow/escalation.py: severity-based routing and SLA/TAT timers (RBI <=30-day), sla_due_ts population on alerts | REAL | BACKEND-19, BACKEND-20 | M |

### M5 Regulatory Generators, External Integration & Edge
*Build the slow-lane EWS/CRILC/FMR generators, regulatory export routes, SIEM and RBI-pipeline integration (scaffolded against live regulator/SIEM endpoints), the API gateway front, and cross-border/DPDP controls.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| BACKEND-24 | EWS / RFA / CRILC / FMR regulatory generators | regulatory/ engine: EWS-framework integration with CBS, RFA tagging, CRILC 3-crore/7-day + 180-day window logic, FMR generation, CFR feed, DAMI-unit support | SCAFFOLD | BACKEND-12, DATABASE-CLICKHOUSE | L |
| BACKEND-25 | Slow-lane entity/credit scoring + RBI EWS/CRILC pipeline feed | regulatory/slow_lane.py producing entity/credit scoring and feeding the RBI EWS/CRILC pipeline for red-flagged accounts | SCAFFOLD | BACKEND-24 | M |
| BACKEND-26 | Regulatory export routes (FMR/CRILC) | report_routes.py: GET /reports/fmr, GET /reports/crilc producing CRILC/FMR-ready exports | REAL | BACKEND-24, BACKEND-3 | S |
| BACKEND-27 | Bi-directional SIEM integration (consume logs / publish alerts) | integrations/siem.py consuming SIEM logs as a source and publishing alerts as a sink (scaffolded against the bank live SIEM) | SCAFFOLD | BACKEND-13 | M |
| BACKEND-28 | API gateway front (auth, rate-limit, routing, observability) | Kong/APISIX gateway config fronting the app APIs with auth, rate-limiting, routing, and observability | REAL | BACKEND-2, PLATFORM-GATEWAY | M |
| BACKEND-29 | Cross-border / DPDP transfer controls & data-principal rights | compliance/ module: PII tokenized before egress with TEE attestation note, transfer documentation + destination-jurisdiction confirmation, and data-principal access/correction/erasure/grievance handling with response SLAs | SCAFFOLD | BACKEND-17, BACKEND-22, PLATFORM-TEE-LLM | M |

**Cross-workstream dependencies:**
- DATABASE-* for the ClickHouse event/analytics store, PostgreSQL case/user metadata DB, and append-only/WORM audit store that backend routes read and write
- DATA-* for the Kafka event topics, Flink enrichment/windowing, and Feast/Redis online feature store that the inference path consumes
- ML-* for trained+registered ONNX model artifacts (L2/L3/L4/L5), the MLflow registry the /models routes drive, the L6 fusion meta-model, and SHAP/reason-code outputs
- FRONTEND-* consumes every API contract (alerts queue, entity-360, explanations, rules UI, model/drift views, regulatory exports) and the RBAC-scoped / unmask semantics
- PLATFORM-* for Keycloak deployment, Vault/Secrets-Manager + HSM/KMS key custody, mTLS/service mesh, API-gateway infra, and TEE LLM egress controls

---

## 🖥️ FRONTEND — Workstream

Delivers the full React+TypeScript investigator console for the insider-fraud system: a foundation app shell with OIDC SSO and RBAC-driven role views, the core investigation surface (triage queue, entity-360 timeline, explanation panel with AI narrative, graph view, peer comparison, EDD action panel feeding the relabeling loop), case management, and the role-specialized compliance/auditor/model-engineer/admin/reporting screens. Every view is a thin client over the BACKEND REST API atop ClickHouse, designed for sub-second drill-down and SAR/FMR-defensible explanations. All 22 inventory items are REAL (CAN_BUILD) with no blockers, consolidated into 13 build tasks.

**Tech:** React 19, TypeScript 5.6, Vite, TanStack Query, TanStack Table/Virtual, React Router, oidc-client-ts / Keycloak adapter, Cytoscape.js (graph view), Recharts/visx (charts), Tailwind/shadcn-ui, Grafana embed (iframe), Playwright (e2e)

### M1 Foundations - app shell, SSO, RBAC
*Stand up the React/TS application skeleton, authenticate users via OIDC SSO, and wire role-based routing/navigation plus a typed API client so all later views plug in cleanly.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| FRONTEND-1 | React+TS app scaffold, design system, typed API client | frontend/ Vite+React19+TS project: src/app shell, src/lib/apiClient.ts (typed wrapper over BACKEND REST + generated types), TanStack Query provider, shadcn/Tailwind design system, routing skeleton | REAL | BACKEND-API, PLATFORM-1 | M |
| FRONTEND-2 | Login / SSO screen with OIDC redirect, MFA, session controls | src/auth/ - oidc-client-ts integration, LoginPage, token refresh, PKCE redirect/callback, session-timeout controls (UI screen 1, blueprint l.946) | REAL | FRONTEND-1, PLATFORM-1, BACKEND-AUTH | M |
| FRONTEND-3 | RBAC-aware routing, role views shell, and audited PII-unmask control | src/auth/rbac.tsx - capability matrix guards, role-scoped route shells for Analyst/Compliance/Auditor/ModelEng/Admin, reusable masked-PII component with audited unmask action (blueprint Part 23 RBAC table, l.877) | REAL | FRONTEND-2, BACKEND-RBAC | M |

### M2 Triage and case workflow
*Deliver the analyst entry point: the ranked/deduplicated triage queue with SLA timers and claim, plus the case-management surface that links alerts and tracks status/notes/history.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| FRONTEND-4 | Triage queue (Analyst home): ranked, deduplicated alerts with filters, SLA/TAT timer, one-click claim | src/views/TriageQueue.tsx - virtualized table over GET /alerts (fused risk x exposure x confidence ordering), filters (status/risk/assignee/type), SLA/TAT countdown, dedup-per-entity grouping, claim/assign actions (UI screen 2; inventory items 6,15) | REAL | FRONTEND-3, BACKEND-ALERTS, ML-FUSION | L |
| FRONTEND-5 | Case management: assignment, status, linked alerts, notes, history | src/views/CaseManagement.tsx + src/views/CaseDetailShell.tsx - case list, assignment/status workflow, linked-alert panel, threaded notes, activity history over case store (UI screen 4; inventory item 17) | REAL | FRONTEND-4, BACKEND-CASES, DATABASE-CASESTORE | M |

### M3 Investigation surface - the alert/case detail
*Build the core single-alert investigation experience: entity-360 timeline, explanation panel with AI narrative, graph/link view, peer comparison, and the EDD action panel that captures every disposition as a label into the relabeling feedback loop.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| FRONTEND-6 | Alert/Case detail layout + header (score, severity, SLA) | src/views/AlertDetail.tsx - composition shell with score/severity/SLA header binding GET /alerts/{id}, hosting the tabbed sub-panels below (UI screen 3 header; inventory item 16) | REAL | FRONTEND-4, BACKEND-ALERTS | M |
| FRONTEND-7 | Entity-360 unified timeline | src/components/Entity360Timeline.tsx - one timeline merging transactions, access events, DB/data activity, and HR context over GET /entities/{id} + /timeline (inventory items 1,7; UI l.948-950) | REAL | FRONTEND-6, BACKEND-ENTITIES, DATA-EVENTMODEL | L |
| FRONTEND-8 | Explanation panel: SHAP, rule provenance, sequence attention, AI narrative | src/components/ExplanationPanel.tsx - SHAP top-features chart, rule/SoD-typology provenance, LAXCAT sequence-attention view, and clearly-labelled TEE-LLM narrative via GET /explanations/{id} + POST /narratives/{id} (inventory item 8; UI l.951) | REAL | FRONTEND-6, BACKEND-EXPLAIN, ML-EXPLAIN, ML-NARRATIVE | L |
| FRONTEND-9 | Graph/link view: beneficiary networks, shared-identity links, collusion subgraphs | src/components/GraphView.tsx - Cytoscape.js interactive subgraph (beneficiary/shared-device-address, maker-checker collusion) with GNNExplainer evidence over GET /entities/{id}/graph (inventory items 9,16; UI l.952) | REAL | FRONTEND-6, BACKEND-GRAPH, ML-GRAPH | L |
| FRONTEND-10 | Peer comparison view | src/components/PeerComparison.tsx - this actor vs peer group on the flagged dimension (distribution/box plots) over GET /entities/{id}/peers (inventory item 10; UI l.953) | REAL | FRONTEND-6, BACKEND-ENTITIES, ML-FUSION | M |
| FRONTEND-11 | EDD action panel + feedback loop and natural-justice/due-process workflow | src/components/EddActionPanel.tsx - structured EDD checklist, actions (escalate / request-block / close-FP / mark-fraud / add-notes), proportionality+human-in-the-loop gating, each disposition posted to /alerts/{id}/disposition + /feedback as a label and surfaced as immutable-audit confirmation (inventory items 0,4,11,16; UI l.954) | REAL | FRONTEND-6, BACKEND-ALERTS, BACKEND-FEEDBACK, ML-FEEDBACK | L |

### M4 Role-specialized views and reporting
*Complete the role-specific consoles: compliance rules/EWS/export workbench, read-only auditor trail, model-engineer registry/drift dashboards, admin console, and the management/board reporting + regulatory export surface.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| FRONTEND-12 | Compliance view: rules/threshold change-control, EWS/RFA coverage, CRILC/FMR export | src/views/ComplianceView.tsx - configurable rules/thresholds editor with change-control over /rules CRUD, EWS/RFA indicator-coverage dashboard, and one-click CRILC/FMR export via /reports/* (inventory items 2,12,18; UI l.956) | REAL | FRONTEND-3, BACKEND-RULES, BACKEND-REPORTS | L |
| FRONTEND-13 | Auditor, model-engineer, admin, and management-KRI reporting views | src/views/{AuditorView,ModelEngineerView,AdminView,ReportingView}.tsx - read-only immutable audit trail (who-viewed-whom/closed-what) over /audit; champion/challenger registry + drift dashboards over /models+/drift on de-identified data; users/roles + rule-deployment + Grafana system-health embed; board-level KRI/trend/coverage reporting dashboards (inventory items 3,12,19,20,21; UI l.955-959) | REAL | FRONTEND-3, BACKEND-AUDIT, BACKEND-MODELS, BACKEND-ADMIN, PLATFORM-GRAFANA, ML-DRIFT | L |

**Cross-workstream dependencies:**
- BACKEND REST API surface: GET/POST /alerts, /entities/{id}/(timeline/graph/peers), /explanations/{id}, POST /narratives/{id}, /feedback, /rules CRUD, /reports/(fmr/crilc), /audit, /models + /drift + /metrics/model, /admin/users (blueprint Part 23.x API table) — every screen is a client of these
- PLATFORM: Keycloak OIDC/OAuth2 issuer + short-lived JWT, MFA, and the Grafana instance embedded in the admin/ops view
- BACKEND: RBAC capability matrix enforcement and the audited PII-unmask permission (POST /entities/{id}/unmask)
- ML: SHAP reason codes, LAXCAT sequence attention, GNNExplainer graph evidence, TEE-LLM narratives, and drift/model-quality metrics that the explanation, graph and model-engineer views render
- DATABASE: ClickHouse-backed timeline/audit queries and the case/alert store the case-management and auditor views read
- DATA: canonical event-model field groups (actor/action/object/context) that the entity-360 timeline visualizes

---

## 🗄️ DATABASE — Workstream

Delivers the full persistence layer for hawk-eye: object store (MinIO/S3) with encryption-at-rest, Postgres (cases/users/governance), Redis (online feature/cache), ClickHouse columnar analytics store with hot-cold tiering and inverted-index search, append-only Kafka + WORM/object-lock immutable audit trail, the MLflow-backed signed model-file registry, and DPDP/RBI-aligned retention tiering. Everything is buildable locally on synthetic data with on-prem-equivalent components (MinIO for S3, local KMS/Vault for keys), swappable 1:1 to AWS managed services later.

**Tech:** ClickHouse, PostgreSQL, Redis, MinIO (S3-compatible), Apache Kafka / Redpanda, MLflow Model Registry, S3 Object-Lock / MinIO object-lock (WORM), SSE-KMS / MinIO SSE + local KMS/Vault, cosign / sigstore (model signing), Docker Compose / Terraform, SQL DDL + Alembic migrations

### M1 Core stores & encryption foundations
*Stand up the primary datastores (object store, Postgres, Redis) with encryption-at-rest and least-privilege access, providing the storage substrate every other workstream writes to.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATABASE-1 | Object store with encryption-at-rest, versioning and RBAC | infra/storage/minio compose + terraform module (S3/MinIO buckets: models, datasets, feature-snapshots, audit-archive) with SSE/SSE-KMS, versioning, least-privilege IAM/RBAC policies | REAL | PLATFORM-1 | M |
| DATABASE-2 | Postgres app/metadata DB and Redis online store | infra/storage/postgres + redis compose/terraform; Postgres schemas (cases, users, model-governance, approvals) via Alembic migrations; Redis instance for Feast online serving/cache with encryption-at-rest config | REAL | PLATFORM-1 | M |

### M2 ClickHouse analytics & investigation store
*Provide the columnar history/investigation store that the canonical event model, features and dashboard query, including hot-cold tiering and log search.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATABASE-3 | ClickHouse columnar store with hot-cold storage tiering | db/clickhouse/ DDL (MergeTree tables for canonical events, alerts, dispositions, feature backfill) + storage_configuration.xml with hot (SSD) / cold (object-store) volume policy and TTL-MOVE tiering | REAL | DATABASE-1, DATA-1 | L |
| DATABASE-4 | Inverted-index log search over ClickHouse | db/clickhouse/indexes.sql adding inverted (full-text) + bloom/skip indices on event payload/text columns; tokenized-search query helpers for the investigation API | REAL | DATABASE-3 | S |

### M3 Immutable WORM audit trail
*Guarantee a tamper-evident, append-only regulator-grade audit trail of all system and investigator activity, persisted to WORM object-lock storage.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATABASE-5 | Append-only Kafka audit topics | infra/audit/kafka topic config (compaction-off, infinite-retention append-only audit topics) + producer schema for audit events (who viewed whom, alert closes, rule/threshold changes) | REAL | DATA-2 | M |
| DATABASE-6 | WORM object-lock store + tamper-evident audit log | services/audit/ writer that sinks Kafka audit topic to object-lock (immutable, compliance-mode) buckets with per-record hash-chaining/Merkle anchoring; covers alerts, dispositions, model versions, feature snapshots, and investigator actions; verification CLI | REAL | DATABASE-1, DATABASE-5 | L |

### M4 Model-file registry & artifact security
*Provide the versioned, signed, encrypted model registry storing every layer's model artifacts with full reproducibility metadata and theft mitigations.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATABASE-7 | Model file-format & transform-chain artifact layout | registry/artifacts/ spec + serializer utils persisting trees (ONNX + native .txt/.cbm/joblib), nets (ONNX + PyTorch checkpoint), and preprocessors/calibrators versioned together as the whole transform chain at object-store paths {layer}/{model}/{version}/ | REAL | DATABASE-1 | M |
| DATABASE-8 | MLflow model registry with signing, encryption & access logging | registry/mlflow/ config + helpers: Staging->Production->Archived stages, artifacts in versioned encrypted-at-rest object-lock buckets, each version records dataset hash/params/metrics/code-commit/approver/cryptographic signature; model signing with signature verified on load; registry access logging (extraction-theft mitigation) | REAL | DATABASE-6, DATABASE-7 | L |

### M5 Retention & archival tiering
*Implement DPDP/RBI-aligned lifecycle that ages data from hot ClickHouse to cold object store to archive across all stores.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| DATABASE-9 | Retention & archival tiering hot->cold->archive | db/retention/ policies + scheduled job: ClickHouse TTL-MOVE to cold object store then archive tier, object-store lifecycle rules, audit-log archival; retention windows parameterized to DPDP retention and RBI record-keeping | REAL | DATABASE-3, DATABASE-6, DATABASE-8 | M |

**Cross-workstream dependencies:**
- PLATFORM-1: base infra / Terraform / Docker-Compose scaffolding, networking, and (later) KMS/HSM and AWS account that DATABASE storage modules deploy onto
- DATA-1: canonical Unified Event Model schema that ClickHouse tables (DATABASE-3) must mirror to avoid train/serve skew
- DATA-2: Kafka ingestion cluster that the append-only audit topics (DATABASE-5) are provisioned alongside
- ML: MLflow model registry (DATABASE-8) is consumed by ML training/serving for model registration, champion/challenger, and signature-verified load
- BACKEND/FRONTEND: investigation API and dashboard query the ClickHouse store + inverted-index search (DATABASE-3/4) and write audit events to the WORM trail (DATABASE-5/6)

---

## 🏗️ PLATFORM — Workstream

Delivers the runnable infra substrate and governance wrapper for hawk-eye: a docker-compose stack of all infrastructure (Kafka, Flink, Redis/Feast, ClickHouse, Postgres, MinIO, ONNX/Triton, Keycloak, Prometheus/Grafana), parameterized Terraform (AWS ap-south-1 + on-prem) and K8s/Helm, zero-trust networking + secrets/KMS/HSM(mock)/TEE-attestation(mock), CI/CD with full security scanning, HA/DR/BCP + SRE observability, and the 24 mocked org/governance/regulatory artifacts seeded into a governance DB and surfaced in the dashboard. The hot-path reference topology and graceful-degradation (rules-only fallback) are real and wire all workstreams together.

**Tech:** docker-compose, Kubernetes/Helm, Terraform 1.9.x, Apache Kafka, Apache Flink, Redis/Feast, ClickHouse, PostgreSQL, MinIO, ONNX Runtime/Triton, Keycloak (OIDC), HashiCorp Vault, SoftHSM (mock HSM), Prometheus/Grafana/OpenTelemetry, ArgoCD + GitHub Actions, Trivy/Syft/Grype (SBOM+CVE), Semgrep (SAST), OPA, mTLS/SPIFFE, Playwright (UAT), FastAPI/Python, Markdown/PDF artifact generators

### M1 Local Foundations (compose stack + reference topology)
*One docker-compose up brings the entire hawk-eye infra online locally with the L0-L7 reference topology wired and version-pinned, giving every other workstream a runnable substrate.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| PLATFORM-1 | Pinned platform version BOM + monorepo/deploy scaffolding | deploy/versions.bom.yaml, repo layout, root Makefile targets | REAL | — | S |
| PLATFORM-2 | Core infra docker-compose: Kafka, Flink, Redis, ClickHouse, Postgres, MinIO, Feast | deploy/compose/docker-compose.core.yml + per-service config | REAL | PLATFORM-1 | L |
| PLATFORM-3 | Serving/app/identity/observability compose: ONNX-Triton, FastAPI app, Keycloak (OIDC), Prometheus, Grafana | deploy/compose/docker-compose.app.yml, keycloak realm + dashboards | REAL | PLATFORM-2 | M |
| PLATFORM-4 | End-to-end reference topology wiring (collectors->Kafka->Flink->Redis/Feast+serving->risk-fusion->alerts topic->case/alert store->ClickHouse+dashboard) with rules-only graceful-degradation switch | deploy/topology/ docs + topic/stream definitions + degradation toggle service | REAL | PLATFORM-2, PLATFORM-3, BACKEND-1, DATA-1, ML-1 | L |
| PLATFORM-5 | Sizing/cost calculator (Kafka brokers, Flink TMs, ClickHouse shards, GPU pool, Redis; AWS instance cost model) | tools/sizing/sizing_calculator.py + sizing.md | REAL | PLATFORM-1 | S |
| PLATFORM-6 | Compute-placement profiles (CPU tree-train, GPU seq/graph-train, CPU inference) as scaffolded resource configs | deploy/profiles/compute-placement.yaml + ADR | SCAFFOLD | PLATFORM-5 | S |

### M2 IaC, Networking, Zero-Trust & Secrets
*Parameterized Terraform/K8s build either AWS (ap-south-1) or on-prem identically, with zero-trust segmentation, least-privilege IAM/service accounts, mTLS, secrets/KMS, and mocked HSM + TEE attestation.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| PLATFORM-7 | Parameterized Terraform modules (target=aws/onprem) + AWS pilot resources (MSK, Managed Flink, ElastiCache, EC2 ClickHouse/serving, RDS, S3 SSE-KMS/object-lock, MWAA, ALB) - terraform plan only, no apply | infra/terraform/ modules + envs/{aws,onprem} | SCAFFOLD | PLATFORM-2, PLATFORM-5 | L |
| PLATFORM-8 | AWS->on-prem component-swap migration map (MSK->Kafka, ElastiCache->Redis, RDS->Postgres, S3->MinIO, KMS->HSM, Secrets Manager->Vault, MWAA->Airflow) + Lightsail-vs-EC2 ADR | infra/terraform/migration-map.md + ADR-0001-ec2-in-vpc.md | REAL | PLATFORM-7 | M |
| PLATFORM-9 | Kubernetes/Helm on-prem manifests for scale/HA/rolling deploys with data-residency (in-India) labels | deploy/k8s/ helm charts + residency-policy labels | SCAFFOLD | PLATFORM-3 | L |
| PLATFORM-10 | Network zero-trust: VPC private subnets + SG/NACL, NAT egress allow-list (NEAR AI/Groq only), tier segmentation, micro-segmentation security zones | infra/terraform/modules/network/ + zero-trust policy docs | SCAFFOLD | PLATFORM-7 | M |
| PLATFORM-11 | Identity, IAM least-privilege roles + least-privilege service accounts + mTLS/SPIFFE between internal services | infra/terraform/modules/iam/ + deploy/mtls/ certs + service-account manifests | SCAFFOLD | PLATFORM-3, PLATFORM-10 | M |
| PLATFORM-12 | Secrets management (Vault dev / AWS Secrets Manager+SSM) + KMS encryption-at-rest + field-level PII key handling integration | deploy/secrets/vault config + terraform kms module | SCAFFOLD | PLATFORM-11 | M |
| PLATFORM-13 | Mock HSM key custody (SoftHSM PKCS#11) for dev key operations | deploy/hsm/softhsm + key-custody service wrapper | MOCK | PLATFORM-12 | M |
| PLATFORM-14 | Mock TEE confidential-compute attestation microservice (dual CPU+GPU quote issuer + verifier endpoint; PII-tokenize-before-egress; on-prem TDX/H200 LLM node profile) | services/tee-attestation/ (issuer+verifier) + onprem-llm-node profile | MOCK | PLATFORM-12 | L |
| PLATFORM-15 | PAM integration shim (mock) for platform-admin sessions + SoD service accounts (no shared accounts) | services/pam-shim/ + admin-access policy doc | MOCK | PLATFORM-11 | S |

### M3 CI/CD, Security Testing & Supply-Chain
*Build/test/deploy pipelines with the full test pyramid, ML+app security scanning, signed artifacts, GitOps promotion, and the mocked VAPT/red-team/UAT artifacts.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| PLATFORM-16 | CI pipeline: lint -> unit/integration/contract -> data-validation -> model behavioral/fairness tests -> security scans -> signed artifacts/images | .github/workflows/ci.yml + test-pyramid harness | REAL | PLATFORM-4 | L |
| PLATFORM-17 | ML supply-chain controls: SBOM (Syft/SPDX/CycloneDX), CVE scan (Grype/Trivy), container scan, model signing, SAST/DAST/IAST (Semgrep), secrets+IaC scanning; pinned deps from internal mirror (scaffold) | ci/security/ pipeline stages + sbom output | SCAFFOLD | PLATFORM-16 | M |
| PLATFORM-18 | CD pipeline: GitOps (ArgoCD), blue-green/canary, auto-rollback on SLO regression, feature flags; dev->staging(masked)->prod parity via IaC | deploy/argocd/ + .github/workflows/cd.yml + env parity configs | REAL | PLATFORM-16, PLATFORM-9 | M |
| PLATFORM-19 | Release + change governance software (versioned releases, release notes, traceability; change-request workflow, risk-form, scheduled-window enforcement, rollback runbook) | tools/release/ + governance/change-mgmt/ workflow | SCAFFOLD | PLATFORM-18 | M |
| PLATFORM-20 | Threat modeling + framework mapping (STRIDE + MITRE ATLAS + insider lens; ML-attack->mitigation table; OWASP ML/Top10, NIST AI RMF/CSF, RBI directions; FREE-AI Sutra->control map) | security/threat-model.md + framework-mapping.md | REAL | PLATFORM-1 | M |
| PLATFORM-21 | Security/perf/chaos test suites (SAST/DAST/IAST + load/soak at target TPS+p99, chaos kill broker/serving node) + attack-on-system SIEM detection rules (extraction queries, abnormal label edits, threshold changes) | tests/{perf,chaos,security}/ + siem/detection-rules/ | REAL | PLATFORM-16, PLATFORM-4 | L |
| PLATFORM-22 | Vulnerability-management programme (continuous scan, risk-ranked remediation, patch SLAs/windows, emergency path) + tracker view | security/vuln-mgmt/ tracker + policy | REAL | PLATFORM-17 | S |
| PLATFORM-23 | Mock VAPT/pentest + ATLAS red-team + model-risk-review reports wired into vuln tracker, tied to model versions | security/reports/{vapt,redteam,model-risk}.md + seeded tracker records | MOCK | PLATFORM-22, PLATFORM-29 | M |
| PLATFORM-24 | Mock investigator UAT: Playwright script driving dashboard triage->entity-360->explanation->disposition, asserting steps, emitting signed UAT report | tests/uat/investigator_uat.spec.ts + uat-report generator | MOCK | FRONTEND-1, PLATFORM-18 | M |

### M4 HA/DR/BCP & SRE Observability
*Resilience, backup/restore, DR failover, BCP graceful-degradation, and full SRE observability (golden signals, tracing, SLOs, on-call, incident management).*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| PLATFORM-25 | HA + multi-AZ/multi-DC redundancy for Kafka/ClickHouse/Redis/app/serving with per-component RTO/RPO + multi-rack replication | deploy/ha/ replication configs + rto-rpo-matrix.md | SCAFFOLD | PLATFORM-9, DATABASE-1 | L |
| PLATFORM-26 | Automated encrypted immutable backups (audit log, model registry) + restore tooling + WORM/object-lock store | ops/backup/ + restore tooling + worm config | REAL | PLATFORM-25, DATABASE-1 | M |
| PLATFORM-27 | DR failover runbooks + scripted restore-drill (backup->teardown->restore->validate row counts->failover toggle->drill report with RTO/RPO timings) + chaos resilience injection | ops/dr/runbooks + scripts/dr-drill.sh + drill-report generator | MOCK | PLATFORM-26, PLATFORM-21 | M |
| PLATFORM-28 | BCP + graceful degradation: board-approved BCP doc (seeded approval) + real rules-only L1 fallback switch | governance/bcp.md + services/degradation-switch (real fallback to L1) | MOCK | PLATFORM-4, BACKEND-1 | M |
| PLATFORM-29 | SRE observability: four golden signals per component, OpenTelemetry tracing, centralized structured logging (ClickHouse/OpenSearch), Prometheus+Grafana, SLO/SLI + error budgets | observability/otel + grafana dashboards + slo-definitions.yaml | REAL | PLATFORM-3 | L |
| PLATFORM-30 | Operational alerting + incident management (PagerDuty/Opsgenie routing severity tiers, incident-commander role, runbooks, blameless post-mortems, RBI/CERT-In reporting) - scaffolded integration | ops/oncall/ alert-routing config + incident-mgmt runbooks | SCAFFOLD | PLATFORM-29 | M |
| PLATFORM-31 | Capacity management + annual capacity-assessment artifact (reviewed-by-ITSC seeded record) | ops/capacity/ assessment + forecast tool | REAL | PLATFORM-5, PLATFORM-29 | S |

### M5 Governance, Regulatory & Org Artifacts (mocked) + Go-Live
*Generate and seed the 24 mocked org/governance/regulatory artifacts into a governance DB, enforce SoD RBAC personas and the human-in-the-loop gate, and aggregate everything into a DB-backed go-live readiness checklist surfaced in the dashboard.*

| ID | Task | Deliverable | Status | Deps | Eff |
|---|---|---|---|---|---|
| PLATFORM-32 | Governance DB schema + artifact-store service (records keyed to model versions/releases, surfaced in dashboard governance view) | governance/db/schema.sql + services/governance-api/ | REAL | PLATFORM-3, DATABASE-1 | M |
| PLATFORM-33 | SoD RBAC personas (builder/labeler/actor/administrator) in Keycloak/JWT with route-level enforcement + segregation of training-data/label/build access | governance/rbac/ keycloak roles + route guards + demo logins | MOCK | PLATFORM-11, PLATFORM-32 | M |
| PLATFORM-34 | Mock model-governance & validation artifacts: model-validation report + simulated independent-validation sign-off gate before prod promotion (seeded approval keyed to model version) | governance/validation/ report generator + sign-off gate + seeded records | MOCK | PLATFORM-32, ML-1, PLATFORM-18 | M |
| PLATFORM-35 | Mock FREE-AI/AI-governance bodies: AI/Model-Risk Committee + ethics committee + board records (rosters, minutes, model-approval/incident-review/board-report rollups) + approval-queue/incident/board-pack software + AI incident-reporting mechanism | governance/committees/ seeded records + services/governance-ui panels | MOCK | PLATFORM-32 | L |
| PLATFORM-36 | Mock policy/regulatory document artifacts: board-approved AI Policy, BCP(ref M4), DPIA/algorithmic-due-diligence, DPO appointment + annual data-protection audit, lawful-basis/DPDP employee-monitoring mapping, breach-notification workflow (CERT-In 6h/DPB/RBI), transparency/works-council/whistleblowing docs | governance/docs/ generated md/pdf + seeded approval records | MOCK | PLATFORM-32 | L |
| PLATFORM-37 | Human-in-the-loop natural-justice gate (holds classification pending human review with proportionality/explanation) + DPIA sign-off binding | services/hitl-gate/ + integration into scoring pipeline | MOCK | PLATFORM-36, BACKEND-1, FRONTEND-1 | M |
| PLATFORM-38 | Mock outsourcing/vendor-risk artifacts (AWS+NEAR AI): due-diligence, SLAs, exit strategy, concentration risk, AI-specific clauses, SBOM linkage | governance/vendor-risk/ seeded vendor records + clause templates | MOCK | PLATFORM-32, PLATFORM-17 | M |
| PLATFORM-39 | Mock operating-model artifacts: org chart, Three-Lines RACI matrix, committee charters, RACI for key activities, steering-committee/RAID/OKR, FinOps (tagging/showback/TCO), per-typology investigation playbooks/SOPs, staffing-model calculator (Erlang headcount/roster), training/change-mgmt program + override-rate/alert-fatigue dashboard panel | governance/operating-model/ artifacts + tools/staffing-calculator + finops + change-mgmt panel | MOCK | PLATFORM-32, PLATFORM-29 | L |
| PLATFORM-40 | Documentation suite: ADRs, runbooks/ops manuals, OpenAPI docs, data dictionary, model cards, SOPs, DR/BCP docs, detection-coverage map, honest-limits statements, bibliography | docs/ consolidated documentation set | REAL | PLATFORM-27, PLATFORM-20 | M |
| PLATFORM-41 | DB-backed go-live readiness checklist aggregating status of ALL mocked artifacts (AI policy, DPO, DPIA, validation sign-off, VAPT, UAT, CAB, reporting-form, BCP, lawful-basis) + threat-intel feedback loop into rules/synthetic library | governance/go-live/checklist service + dashboard view + threat-intel feed | MOCK | PLATFORM-23, PLATFORM-24, PLATFORM-34, PLATFORM-35, PLATFORM-36, PLATFORM-38, PLATFORM-39 | M |

**Cross-workstream dependencies:**
- BACKEND services (rules/scoring/risk-fusion gateways, FastAPI app) are containerized and deployed by PLATFORM compose/K8s/CI-CD
- DATA streaming jobs (Flink feature compute) and connectors run on PLATFORM's Kafka/Flink/Feast/ClickHouse infra
- ML model-serving (ONNX/Triton), MLflow registry, and training DAGs (Airflow) run on PLATFORM compute/orchestration
- FRONTEND React dashboard is built/deployed by PLATFORM (S3+CloudFront / app-served) and consumes the governance views PLATFORM seeds
- DATABASE schemas (ClickHouse analytics, Postgres cases/governance, WORM audit) are provisioned/replicated by PLATFORM HA/DR
- Governance go-live checklist aggregates artifact status produced across ALL workstreams

---

*Generated from the blueprint implementability audit. 380 inventory items consolidated into 149 build tasks. Update task status as work lands.*