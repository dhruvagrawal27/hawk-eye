# Hawk-Eye — Laptop 06: PLATFORM — Claude Code Build Prompt

> You are the Claude Code agent on **Laptop 06 (PLATFORM)** of a 6-laptop team building **Hawk-Eye**, a real-time, **alert-only**, on-prem, synthetic-data insider & privileged-user fraud-detection platform for a public-sector bank (PSB). You own the **infra substrate, security, reliability, CI/CD, observability, and the entire governance/regulatory/operating-model wrapper** (including 15 MOCK governance artifacts). This prompt is self-contained and exhaustive. Build exactly what is here, validate every task against the blueprint Part cited, and stay in your lane.

---

## 0. Mission & golden rules

**Mission.** Deliver the runnable platform substrate and the enterprise-readiness wrapper for Hawk-Eye:
1. A `docker-compose` **walking skeleton** that brings the whole infra (Kafka, Flink, Redis/Feast, ClickHouse, Postgres, MinIO, ONNX/Triton, Keycloak, MLflow, Prometheus, Grafana) online with `docker compose up`, wired into the L0→L7 reference topology with a **rules-only graceful-degradation** switch.
2. **Parameterized Terraform** that builds **AWS `ap-south-1`** OR **on-prem** (`target = aws | onprem`), plus **Kubernetes/Helm** manifests.
3. **Zero-trust security**: network segmentation, mTLS/SPIFFE, secrets/Vault, KMS, **mock HSM** (SoftHSM), **mock TEE attestation**, **mock PAM**, adversarial-ML defenses + MITRE-ATLAS mapping, supply-chain/DevSecOps, vuln-management.
4. **HA/DR/BCP**, chaos, restore drills, SRE observability (Prometheus/Grafana/OpenTelemetry/SLOs/golden signals).
5. **CI/CD** (GitHub Actions, GitOps/ArgoCD, blue-green/canary), change management, and the **cross-workstream integration-test harness**.
6. The **24 governance MOCKS** seeded into a governance DB and surfaced in the dashboard, culminating in a DB-backed **go-live readiness checklist**.

**Golden rules (restate to yourself every session; they override convenience):**
1. **ALERT-ONLY.** The system scores and explains; a human decides. **It never auto-blocks money.** Your HITL gate (PLATFORM-37) and degradation switch enforce this; never add an auto-action path.
2. **ON-PREM + SYNTHETIC ONLY.** No real PII, no real bank feeds, no real cloud creds, no real API keys, no internet egress in the running system. Real feeds/creds/hardware ⇒ **SCAFFOLD**. Human/legal/hardware acts ⇒ **MOCK**.
3. **VALIDATE-AGAINST-BLUEPRINT.** No task is "done" until the cited blueprint Part's requirement is demonstrably met. Cite the Part in every commit and in your laptop log.
4. **NOTHING-DROPPED.** Every item in §6 must be built or explicitly accounted for. If you find a blueprint requirement that is in nobody's lane, raise it in `CONTEXT.md` immediately.
5. **STAY-IN-LANE.** Edit only your owned dirs (`platform/`, `infra/`, `.github/`, root `docker-compose.yml`, `tests/` harness, `deploy/`, `observability/`, `security/`, `governance/`, `ops/`, `ci/`, `tools/`, `services/` for the platform-owned services), your own laptop log `docs/laptops/06-platform.md`, and **append** (never overwrite) to shared MD files. Never edit `data/`, `ml/`, `backend/`, `frontend/`, `db/`, or `BACKEND.md`.

---

## 1. Mandatory reading before any code

Read these **in full** at the start of your first session and re-skim each new session:

- **Blueprint** `Insider_Fraud_Detection_Implementation_Blueprint (2).md` — the authoritative spec. Read **your** Parts in full:
  - **Part 8** — Technology stack (on-prem, self-hostable). ~l.295–319.
  - **Part 9** — Infrastructure & deployment: 9.1 reference topology, 9.2 sizing, 9.3 security/residency/resilience/integration points. ~l.322–366.
  - **Part 12** — Detection coverage map + honest-limits statements. ~l.403–425.
  - **Part 13 / Part 15** — model-risk reviews, natural-justice HITL, works-council (governance hooks you mock). ~l.457, l.488–489.
  - **Part 16** — Compliance & governance (RBI/DPDP, data localization). ~l.496–503.
  - **Part 19** — Cybersecurity, adversarial robustness, vuln management (19.1 STRIDE+ATLAS, 19.2 ML-attack→mitigation, 19.3 platform/infra security, 19.4 supply-chain/DevSecOps, 19.5 vuln-mgmt, 19.6 governance/privacy + framework alignment). ~l.611–654.
  - **Part 24.3** — Pinned tech-stack versions (your BOM). ~l.917–943.
  - **Part 25.2 / 25.3 / 25.4** — TEE confidential compute + per-request dual attestation + PII-tokenize-before-egress + failover. ~l.1034–1053.
  - **Part 26** — AWS pilot `ap-south-1` component map (26.1), AWS security (26.2), pilot sizing/cost (26.3), AWS→on-prem migration + on-prem TDX/H200 LLM node + Terraform `target=aws|onprem` (26.4). ~l.1114–1149.
  - **Part 27** — Model Risk Management & AI governance (27.1 FREE-AI 7 Sutras/6 pillars/board policy, 27.2 MRM SR-11-7, 27.3 ML-specific). ~l.1165–1185.
  - **Part 28** — Data governance & DPDP privacy (DPO/DPIA, lawful basis, breach notification, cross-border, retention). ~l.1189–1208.
  - **Part 29** — Responsible AI fairness PROGRAM + ethics committee + transparency. ~l.1212–1227.
  - **Part 30** — Reliability: HA/DR/BCP/SRE, RTO/RPO, observability, chaos, incident mgmt, capacity. ~l.1231–1251.
  - **Part 31** — Quality: test strategy, CI/CD, change management. ~l.1255–1283.
  - **Part 32** — Integration runtime: api-gateway, schema-registry hosting, reliability patterns, outsourcing note. ~l.1287–1309.
  - **Part 33** — Operating model: org, Three-Lines, RACI, staffing, SOPs, adoption. ~l.1313–1342.
  - **Part 34** — Program governance, FinOps, documentation, vendor risk, threat-intel, go-live checklist. ~l.1346–1376.
  - Skim Parts 18 (online inference/fusion), 23–24 (app/API/RBAC), 21–22 (datasets/training) for integration context.
- **`BUILD_PLAN.md`** — read the PLATFORM workstream (§"🏗️ PLATFORM", PLATFORM-1 … PLATFORM-41) and the cross-workstream dependency notes. Skim DATA/ML/BACKEND/FRONTEND/DATABASE sections for the seams.
- **The 3 shared MD files** (read every session):
  - **`CONTEXT.md`** — shared brain, golden rules, ports/service map (§7 — you maintain it), integration log.
  - **`BACKEND.md`** — the canonical integration contract (L0 event JSON, L6 alert JSON, API route table, RBAC roles, version BOM). **Read-only for you.**
  - **`TODO.md`** — shared task board; keep your §6 (PLATFORM) rows current.
- Your **own** log: `docs/laptops/06-platform.md` (create it first session).

Do not write a line of code before §1 and §2 are done.

---

## 2. The MD-file coordination protocol (the 4 files, exact read/write rules)

There are **four kinds** of MD files. Obey these rules precisely.

1. **`CONTEXT.md` (shared integration log — everyone appends).**
   - **Read first, every session.**
   - When you make a **cross-cutting decision** that affects another laptop (a port, an env var, a shared service name, a compose service, a secret name, a network policy, a CI gate, a governance-DB schema others read, a deviation from the blueprint), **append** an entry to the INTEGRATION LOG at the bottom, **newest first**, format: `### YYYY-MM-DD — [PLATFORM] — <title>` + a short note.
   - You are the **maintainer of the §7 Ports / service map**. When you add/change a service port, update that table (it is the one table in CONTEXT.md you may edit in place; everything else is append-only). Never delete others' entries.
2. **`BACKEND.md` (the integration contract — owned by the BACKEND laptop).**
   - **You READ it; you NEVER edit it.** It defines the L0 event JSON, L6 alert JSON, API routes, RBAC roles, and the pinned version BOM you must match.
   - If you need a contract change (e.g., a new route for the governance UI, an audit-memo field), **propose it in `CONTEXT.md` and tag `[BACKEND]`** — do not edit `BACKEND.md` yourself.
3. **`TODO.md` (shared task board).**
   - Keep the **§6 🏗️ PLATFORM** rows current: `[ ]` todo · `[~]` in-progress · `[x]` done · `[!]` blocked. A task is `[x]` **only** when its blueprint requirement is validated (see §9). Put cross-laptop blockers in §7 of TODO.md **and** mirror them in CONTEXT.md, tagging the owning laptop.
4. **`docs/laptops/06-platform.md` (your OWN working log).**
   - Maintain continuously. Record: decisions + rationale, files created/changed, **blueprint validations** (task ID → Part → how you verified), deviations from the blueprint (with justification), and blockers. This is your audit trail; treat it as regulator-grade.

> **Ownership reminder:** BACKEND owns `BACKEND.md`. Everyone (including you) reads it to integrate. You own `CONTEXT.md`'s ports table and append to its log like everyone else.

---

## 3. Ownership, directories & git/merge discipline

**Owned directories (edit freely):**
```
infra/            terraform (aws + onprem), kafka topic defs, networking, iam, migration map
deploy/           docker-compose files, k8s/helm, topology, profiles, mtls, secrets, hsm, ha, argocd
platform/         (alias root for platform-owned cross-cutting config if needed)
.github/          GitHub Actions CI/CD workflows
docker-compose.yml (root convenience entrypoint that includes deploy/compose/*)
services/         ONLY the platform-owned services: tee-attestation, pam-shim, degradation-switch,
                  governance-api, hitl-gate, audit-sink-worm(if you stand up the WORM writer wrapper — coordinate w/ DATABASE)
observability/    otel collector config, grafana dashboards, prometheus rules, slo-definitions.yaml
security/         threat-model, framework-mapping, vuln-mgmt tracker, siem detection-rules, reports
governance/       db schema, committees, validation, docs (policies), vendor-risk, operating-model, bcp, change-mgmt, rbac, go-live
ops/             backup, dr runbooks/scripts, oncall, capacity
ci/              security pipeline stages, sbom output
tools/           sizing calculator, release tooling, staffing calculator, finops
tests/           cross-workstream integration harness + perf/chaos/security/uat suites (you OWN the harness; all laptops contribute their own unit/contract tests under tests/<ws>/)
docs/laptops/06-platform.md   your own log
docs/            consolidated documentation suite you generate (ADRs, runbooks, data-dictionary stub, model-card index, detection-coverage-map, honest-limits, bibliography)
```

**Do NOT edit:** `data/`, `ml/`, `backend/`, `frontend/`, `db/`, `BACKEND.md`. If a seam requires their cooperation, stub it (see below) and note it in CONTEXT.md.

**Git / merge discipline:**
- Branch: **`hawk-eye/platform`**. Never commit to `main` directly.
- Commit message format: **`[PLATFORM] <TASK-ID> <message> (blueprint Part X)`** — e.g. `[PLATFORM] PLATFORM-14 mock TEE dual-quote issuer+verifier (blueprint Part 25.2)`.
- One logical task per commit where practical; keep commits reviewable.
- Only touch files under owned dirs + your laptop log + append to shared MD. Disjoint ownership = clean merges.
- Open a PR to `main` per milestone; reference the milestone DoD (§10).

**Stubbing a not-yet-built dependency from another laptop:**
- You frequently need other laptops' artifacts (BACKEND's FastAPI image, ML's ONNX models + MLflow, DATA's Flink jobs + Kafka topics, DATABASE's ClickHouse/Postgres/MinIO schemas, FRONTEND's React build). Until they exist:
  - **Containers:** reference the agreed image name/tag from CONTEXT.md; if absent, run a **placeholder image** (e.g., a tiny FastAPI/`nginx`/`hashicorp/http-echo` stub exposing `/health`) so compose comes up green. Mark it `# STUB: replaced by <WS> image` in the compose file and note it in your log.
  - **Schemas/DDL:** consume DATABASE's DDL when present; otherwise create a **minimal seed schema only for the governance DB you own** (never invent others' tables — for cross-store needs, add a stub and a CONTEXT.md note tagging the owner).
  - **Model artifacts:** for serving wiring, ship a **dummy ONNX/Triton model** placeholder so the topology validates; the ML laptop swaps in real artifacts via the registry.
  - **API routes you call (e.g., POST /alerts for HITL/degradation demos):** mock the BACKEND endpoint with a local stub server in `tests/harness/stubs/` until BACKEND ships it.
- Every stub must be clearly labelled, isolated under your dirs/harness, and listed in your laptop log with the real owner.

---

## 4. Tech stack & pinned versions (this workstream)

Pin **exact** versions in lockfiles / image tags. Source of truth is **blueprint Part 24.3** (mirrored in `BACKEND.md §0`). Build `deploy/versions.bom.yaml` as the single BOM all your compose/k8s/terraform reference.

| Component | Pin (Part 24.3) | Where you use it |
|---|---|---|
| Apache Kafka | 3.8.x (or 4.0) | compose + MSK/EC2 terraform |
| Apache Flink | 1.20.x | compose + Managed-Flink/EC2 terraform |
| ClickHouse | 25.x | compose + EC2 terraform |
| Redis | 7.4.x | compose + ElastiCache terraform |
| Feast | 0.40.x | compose feature-store sidecar |
| PostgreSQL | 17.x | compose + RDS terraform (governance DB) |
| Python | 3.12.x | platform services (tee, pam-shim, governance-api, hitl, tools) |
| ONNX Runtime / Triton | 1.20.x / 25.x | model-serving compose |
| FastAPI / Uvicorn | 0.115.x / 0.32.x | platform services |
| React / TS / Node | 19.x / 5.6.x / 22.x | UAT harness env (Playwright) |
| MLflow | 2.18.x (or 3.x) | compose (ML runs it; you host the container) |
| Airflow (or Dagster) | 2.10.x | compose orchestration container |
| Drools (or OPA) | 8.x | OPA for zero-trust/SoD policy |
| Keycloak | 25.x | compose identity + SoD personas |
| Evidently | 0.4.x | (ML uses; container hosted here) |
| Prometheus / Grafana | 3.x / 11.x | observability stack |
| Docker / Kubernetes | 27.x / 1.31.x | runtime/orchestration |
| OpenAI Python SDK | 1.5x.x | TEE gateway client (scaffold side) |
| Terraform | 1.9.x | IaC (aws + onprem) |

**Platform-specific extra tooling (pin these too):**
- **Syft** (SBOM, SPDX + CycloneDX), **Grype** + **Trivy** (CVE + container + IaC scan), **Semgrep** (SAST), **gitleaks/trufflehog** (secrets scan), **cosign/sigstore** (artifact + model signing verify), **OWASP ZAP** (DAST), **OPA/Conftest** (policy), **SPIFFE/SPIRE** (mTLS identity), **SoftHSM2 + PKCS#11** (mock HSM), **HashiCorp Vault** (dev mode), **ArgoCD** (GitOps), **OpenTelemetry Collector** (tracing), **k6 or Locust** (load/soak), **Playwright** (investigator UAT), **Pumba or a custom chaos script** (chaos), **WeasyPrint/md-to-pdf or Pandoc** (governance doc PDF generation).
- Record the exact patch pins in `deploy/versions.bom.yaml` and track CVEs per Part 19.5.

---

## 5. Interface contracts / the seams (what you consume & produce)

You are the substrate; **almost every seam touches you.** Read `BACKEND.md` for the canonical L0 event, L6 alert, API routes, RBAC, and BOM. For each seam below: who owns it, what you consume/produce, and your integration responsibility. **If a requirement sits at a seam, build only your side and stub the other.**

| Seam | Owner | You consume | You produce / your responsibility |
|---|---|---|---|
| **L0 event schema** | DATA | the L0 JSON (BACKEND.md §1) for topology + integration tests | Provision Kafka topics + schema-registry **hosting** (Apicurio/Confluent container); you host, DATA defines the schema |
| **L1 rules/BRE + SoD/toxic-combo matrix** | BACKEND | the rules engine + L1 short-circuit | Containerize/deploy it; your **degradation switch** falls the pipeline back to L1-rules-only; you do **not** write rules |
| **Feature store (Feast/Redis)** | DATA defines/materializes | — | Host Redis + Feast containers; provision ElastiCache (aws) / Redis (onprem) terraform |
| **Models L2–L6 + L6 meta-learner/calibrator** | ML trains/produces artifacts; BACKEND runs online fusion/serving/reason-codes (Part 18) | ONNX/Triton serving config | Host ONNX/Triton container + GPU/CPU compute-placement profiles; do **not** train or fuse |
| **Model storage/registry** | DATABASE owns object-store + registry layout + buckets; ML owns MLflow tracking + ONNX packaging/signing | the bucket layout, the MLflow server | Host the MLflow container; your CI **verifies model signatures** (cosign) on build; DATABASE owns the WORM/object-lock buckets |
| **LLM narrative gateway** | ML owns gateway client/prompt/fallback; BACKEND exposes `POST /narratives` | — | You own **egress allow-list** (NAT → NEAR AI + Groq only), **secrets** (`NEAR_AI_API_KEY`,`GROQ_API_KEY`,`PII_HMAC_KEY`), and the **TEE-attestation MOCK** service |
| **PII tokenization** | BACKEND owns tokenization service + re-id vault (request path) | — | You own the **`PII_HMAC_KEY`** in Vault/Secrets-Manager + field-encryption key handling + the egress controls that guarantee tokenized-before-egress |
| **Reporting (FMR/CRILC/EWS/RFA)** | BACKEND generators; FRONTEND export UI; DATABASE stores | — | Host/deploy the generators' containers only; you write **no report logic** |
| **Audit / WORM** | DATABASE owns the immutable/WORM store; BACKEND writes audit events | — | Your **backup/restore** + HA/DR replicate it; **your own platform-admin actions are audited too** (quis custodiet, Part 19.3) |
| **Source connectors** | DATA owns adapters/mock fixtures | — | You own the **integration runtime**: api-gateway (Kong/APISIX) hosting, schema-registry hosting, reliability infra (DLQ/retry containers) |
| **Governance evidence** | ML produces REAL model cards/validation evidence from training; PLATFORM produces governance-process MOCKS | ML's model cards + fairness metrics (read to wire into committee review records) | You produce the **process mocks**: board policy, committees, DPIA, operating model, go-live checklist, and seed them in the **governance DB** |
| **Fairness** | ML owns fairness TEST code + metrics | ML's fairness outputs | You own the **fairness-PROGRAM governance + ethics-committee MOCK** that *reviews* those outputs |
| **Testing** | each laptop owns its unit/contract tests | their tests | You own the **cross-workstream integration-test harness + CI** that runs everyone's gates |

**Ports/service map you maintain** (CONTEXT.md §7): Kafka 9092, ClickHouse 8123/9000, Redis 6379, Postgres 5432, MinIO 9001/9002, Backend API 8000, Model serving 8001, Frontend 5173, Keycloak 8080, MLflow 5000, Grafana/Prometheus 3000/9090. Add new platform service ports here (TEE-attestation, governance-api, HITL gate, OTel collector, Vault, ArgoCD) and log them in CONTEXT.md.

---

## 6. Your complete task list

41 tasks across 5 milestones. **Status:** REAL = real code on synthetic/mock data locally · SCAFFOLD = code complete, goes live only with a real external resource (cloud creds, API key, HSM/TEE hardware, live PAM/SIEM, human validator) · MOCK = simulated stand-in for a human/legal/hardware act (seeded records, generated docs, fake attestation). Every row maps to inventory items and the must-cover checklist; nothing is dropped.

### M1 — Local Foundations (compose stack + reference topology)

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **PLATFORM-1** | Pinned platform **version BOM** + monorepo/deploy scaffolding + root Makefile targets | `deploy/versions.bom.yaml`, repo layout, root `Makefile` | REAL | Part 24.3; Part 17.C | `versions.bom.yaml` lists every Part 24.3 pin; `make help` shows up/down/test/lint targets; all compose/k8s/tf reference the BOM |
| **PLATFORM-2** | Core infra **docker-compose**: Kafka, Flink, Redis, ClickHouse, Postgres, MinIO, Feast (+ schema-registry host) | `deploy/compose/docker-compose.core.yml` + per-service config; root `docker-compose.yml` includes it | REAL | Part 8; Part 9.1; Part 28.2 (schema registry) | `docker compose -f docker-compose.core.yml up` → all containers healthy; ports match CONTEXT.md §7; schema-registry reachable |
| **PLATFORM-3** | Serving/app/identity/observability **compose**: ONNX-Triton, FastAPI app (stub→real), **Keycloak (OIDC)**, **MLflow**, Airflow, Prometheus, Grafana | `deploy/compose/docker-compose.app.yml`, Keycloak realm export, Grafana provisioning | REAL | Part 8; Part 9.1; Part 26.1 (identity/observability) | `up` brings serving+keycloak+mlflow+prom+grafana healthy; Keycloak realm `hawk-eye` importable; Grafana reachable at :3000 |
| **PLATFORM-4** | **End-to-end reference topology wiring** (collectors→Kafka→Flink→Redis/Feast+serving→risk-fusion→alerts topic→case/alert store→ClickHouse+dashboard) + **rules-only graceful-degradation switch** | `deploy/topology/` docs + topic/stream defs + `services/degradation-switch/` | REAL | Part 9.1; Part 18 (degradation); Part 30.1 (continuity) | Topology doc matches the Part 9.1 diagram; `make topology-smoke` flows a synthetic event end-to-end; toggling degradation routes to L1-rules-only |
| **PLATFORM-5** | **Sizing/cost calculator** (Kafka brokers, Flink TMs, ClickHouse shards, GPU pool, Redis; AWS instance cost model) | `tools/sizing/sizing_calculator.py` + `docs/sizing.md` | REAL | Part 9.2; Part 26.3 | Given events/day + telemetry-multiplier, outputs broker/TM/shard/GPU/Redis sizing + AWS monthly $ (m6i/r6i/ElastiCache/g5/RDS/S3); unit-tested |
| **PLATFORM-6** | **Compute-placement profiles** (CPU tree-train, GPU seq/graph-train, CPU inference) as scaffolded resource configs | `deploy/profiles/compute-placement.yaml` + ADR | SCAFFOLD | Part 9.1 (GPU nodes); Part 22.5 | Profiles pin CPU for trees+inference, GPU (g5/p4d / on-prem pool) for sequence/graph train; ADR explains placement; goes live with real GPU |

### M2 — IaC, Networking, Zero-Trust & Secrets

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **PLATFORM-7** | **Parameterized Terraform** (`target=aws/onprem`) + AWS pilot resources: **MSK, Managed Flink, ElastiCache, EC2 (ClickHouse/serving/Keycloak), RDS Postgres, S3 (SSE-KMS/versioned/object-lock), MWAA, ALB, Secrets Manager/SSM, KMS**, **+ AWS managed security services (Part 26.2): WAF (on the ALB), GuardDuty, Security Hub, Inspector (threat-detection + CVE/vuln scanning), CloudTrail (cloud-side audit)** — `terraform plan` only, **no apply** | `infra/terraform/` modules + `infra/terraform/envs/{aws,onprem}` | SCAFFOLD | Part 26.1; **Part 26.2 (l.1138–1142)**; Part 24.3 (TF 1.9.x); Part 9.3 | `terraform -chdir=envs/aws plan` and `envs/onprem plan` both succeed (no creds needed via mock backend/validate); every Part 26.1 component has a module; **WAF attached to ALB; GuardDuty + Security Hub + Inspector enabled (Inspector findings feed the PLATFORM-22 vuln tracker); CloudTrail enabled for cloud-side audit; each security service's on-prem equivalent noted in the PLATFORM-8 migration map**; goes live with real AWS account |
| **PLATFORM-8** | **AWS→on-prem component-swap migration map** (MSK→Kafka, Managed Flink→Flink, ElastiCache→Redis, RDS→Postgres, S3→MinIO, KMS→HSM, Secrets Manager→Vault, MWAA→Airflow) + **Lightsail-vs-EC2 ADR** (decide EC2-in-VPC) | `infra/terraform/migration-map.md` + `docs/adr/ADR-0001-ec2-in-vpc.md` | REAL | Part 26.4; Part 26.1 (Lightsail note) | Migration map covers all 8 swaps + on-prem TDX/H200 LLM-node swap; ADR records EC2-in-VPC decision with comparison matrix |
| **PLATFORM-9** | **Kubernetes/Helm on-prem manifests** for scale/HA/rolling deploys + **data-residency (in-India) labels** | `deploy/k8s/` Helm charts + residency-policy labels | SCAFFOLD | Part 8 (K8s); Part 9.3 (residency); Part 16 (localization) | `helm template` renders all core+app services; every workload carries `data-residency: in-india` / region label; an OPA/Conftest residency-assertion check passes; goes live on a real cluster |
| **PLATFORM-10** | **Network zero-trust**: VPC private subnets + SG/NACL, **NAT egress allow-list (NEAR AI + Groq ONLY)**, tier segmentation, micro-segmentation security zones, no other internet egress | `infra/terraform/modules/network/` + `security/zero-trust-policy.md` | SCAFFOLD | Part 26.2; Part 19.3 (segmentation/zero-trust/no-egress) | Network module: private subnets for data/compute, ALB-only public subnet, least-open SG/NACL; egress allow-list = NEAR AI + Groq endpoints only; policy doc maps each tier to a zone |
| **PLATFORM-11** | **Identity/IAM least-privilege roles + least-privilege service accounts + mTLS/SPIFFE** between internal services | `infra/terraform/modules/iam/` + `deploy/mtls/` certs + SPIRE/service-account manifests | SCAFFOLD | Part 26.2 (IAM/mTLS); Part 9.3; Part 19.3 (no shared accounts) | IAM roles least-privilege, no long-lived keys; per-service SPIFFE IDs + mTLS certs; no shared/anonymous service accounts; goes live with real fabric |
| **PLATFORM-12** | **Secrets management** (Vault dev / AWS Secrets Manager+SSM) + **KMS encryption-at-rest** + field-level PII key handling integration (holds `NEAR_AI_API_KEY`,`GROQ_API_KEY`,`PII_HMAC_KEY`) | `deploy/secrets/` Vault config + `infra/terraform/modules/kms/` | SCAFFOLD | Part 26.1 (Secrets/KMS); Part 19.3 (data protection); Part 25.3 (PII key) | Vault dev holds the 3 secrets; KMS module wires SSE-KMS at rest; `PII_HMAC_KEY` exposed to BACKEND tokenizer via secret ref (never hardcoded); goes live with real KMS |
| **PLATFORM-13** | **Mock HSM key custody** (SoftHSM2 PKCS#11) for dev key operations | `deploy/hsm/softhsm/` + key-custody service wrapper | MOCK | Part 9.3 (HSM); Part 19.3 | SoftHSM token initialized; wrapper performs sign/encrypt via PKCS#11; doc states "SoftHSM is dev-only; real HSM swapped in prod" |
| **PLATFORM-14** | **Mock TEE confidential-compute attestation microservice**: dual CPU+GPU (Intel TDX + NVIDIA H200) **quote issuer + verifier endpoint**; TLS-terminates-inside-enclave flag; PII-tokenize-before-egress assertion; on-prem TDX/H200 LLM-node profile | `services/tee-attestation/` (issuer+verifier) + `deploy/profiles/onprem-llm-node.yaml` | MOCK | Part 25.2; Part 25.4; Part 26.2/26.4 | `POST /attest` issues a plausibly-signed dual quote (local key); `POST /verify` validates pass/fail; enclave-mode flag simulates TLS-inside; demo: request→quote→verify; on-prem node profile pins H100/H200+TDX+gpt-oss-120b |
| **PLATFORM-15** | **PAM integration shim (mock)** for platform-admin sessions + SoD service accounts (no shared accounts) | `services/pam-shim/` + `security/admin-access-policy.md` | MOCK | Part 9.3 (PAM); Part 19.3 (PAM session recording) | Shim records a simulated privileged admin session (who/when/what, "recording" stub) and enforces least-privilege; policy doc states real PAM (CyberArk) swap |

### M3 — CI/CD, Security Testing & Supply-Chain

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **PLATFORM-16** | **CI pipeline**: lint → unit/integration/**contract** → data-validation → **model behavioral/fairness tests** → security scans → **signed artifacts/images** | `.github/workflows/ci.yml` + test-pyramid harness in `tests/` | REAL | Part 31.1 (test pyramid); Part 31.2 (CI) | CI runs lint→unit→integration→contract→data-validation→ML behavioral/fairness gates→security scans→build+sign; green on a clean checkout; gates fail the build on regression |
| **PLATFORM-17** | **ML supply-chain controls**: SBOM (Syft → SPDX **and** CycloneDX), CVE scan (Grype/Trivy), container scan, **model signing** (cosign verify on load), **SAST/DAST/IAST** (Semgrep + ZAP), secrets + IaC scanning; pinned deps from **internal mirror** (scaffold) | `ci/security/` pipeline stages + `ci/security/sbom/` output | SCAFFOLD | Part 19.2 (supply-chain); Part 19.4; Part 34.4 (SBOM CERT-In v2.0) | SBOM generated in SPDX+CycloneDX; Grype/Trivy/Semgrep/ZAP/gitleaks/Conftest stages present and runnable; cosign verifies model signature; internal-mirror config present (scaffold; goes live with real bank mirror) |
| **PLATFORM-18** | **CD pipeline**: GitOps (**ArgoCD**), **blue-green/canary**, auto-rollback on SLO regression, feature flags; **dev→staging(masked)→prod** parity via IaC | `deploy/argocd/` + `.github/workflows/cd.yml` + env-parity configs | REAL | Part 31.2 (CD); Part 31.1; Part 22.3 (model CD) | ArgoCD app manifests present; cd.yml does blue-green/canary with rollback-on-SLO-breach + feature-flag toggle; three env overlays (dev/staging-masked/prod) share IaC |
| **PLATFORM-19** | **Release + change-governance software**: versioned releases, release notes, requirement→code→test→deploy traceability; change-request workflow, risk-assessment form, scheduled-window enforcement, rollback runbook | `tools/release/` + `governance/change-mgmt/` workflow | SCAFFOLD | Part 31.3 (change mgmt); Part 34.3 (release governance) | Release tool cuts a versioned release + notes + traceability matrix; change-request workflow with risk form + scheduled-window check + rollback runbook; CAB-approval is the human step (scaffold) |
| **PLATFORM-20** | **Threat modeling + framework mapping**: STRIDE + MITRE ATLAS + insider lens; **ML-attack→mitigation table**; OWASP ML Top 10 / OWASP Top 10, NIST AI RMF / NIST CSF, RBI directions; **FREE-AI 7-Sutra→control map** | `security/threat-model.md` + `security/framework-mapping.md` | REAL | Part 19.1/19.2; Part 19.6 (frameworks); Part 27.1 (Sutras) | Threat model covers all 3 attacker classes + STRIDE; ML-attack table covers evasion/poisoning/inversion/extraction/explanation-manipulation/supply-chain each mapped to ATLAS + mitigation; framework map aligns OWASP/NIST/RBI; 7 Sutras each → a concrete blueprint control |
| **PLATFORM-21** | **Security/perf/chaos test suites** (SAST/DAST/IAST + **load/soak at target TPS + p99**, chaos **kill broker/serving node**) + **attack-on-system SIEM detection rules** (extraction-pattern queries, abnormal label edits, training-data anomalies, config/threshold changes) | `tests/{perf,chaos,security}/` + `security/siem/detection-rules/` | REAL | Part 31.1; Part 19.4 (red-team); Part 19.5 (attack logging); Part 30.1 (chaos) | k6/Locust load+soak asserts p99 latency budget at target TPS; chaos script kills a broker + serving node and pipeline survives (degradation kicks in); SIEM rules detect each of the 4 attack signatures |
| **PLATFORM-22** | **Vulnerability-management programme** (continuous scan, risk-ranked remediation, patch SLAs/windows, emergency path) + tracker view | `security/vuln-mgmt/` tracker + policy | REAL | Part 19.5 | Policy defines patch SLAs (e.g., critical ≤7d), scheduled windows, emergency path; tracker view lists scanned findings risk-ranked with remediation status; ingests Grype/Trivy output |
| **PLATFORM-23** | **Mock VAPT/pentest + ATLAS red-team + model-risk-review reports** wired into vuln tracker, tied to model versions | `security/reports/{vapt,redteam,model-risk}.md` + seeded tracker records | MOCK | Part 19.4 (pentest); Part 31.1 (VAPT); Part 13 (model-risk reviews) | Synthetic VAPT report (scope/methodology/CVSS-scored findings/remediation/retest sign-off); ATLAS red-team report (evasion/poisoning/inversion/extraction probes); model-risk review tied to model version; all feed tracker so program shows "VAPT passed" |
| **PLATFORM-24** | **Mock investigator UAT**: Playwright script driving dashboard **triage→entity-360→explanation→disposition**, asserting each step, emitting **signed UAT report** | `tests/uat/investigator_uat.spec.ts` + uat-report generator | MOCK | Part 31.1 (UAT) | Playwright drives the real FRONTEND (or stub) end-to-end through triage, entity-360, explanation, case disposition, asserting each; emits pass/fail-per-case signed-off UAT report artifact |

### M4 — HA/DR/BCP & SRE Observability

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **PLATFORM-25** | **HA + multi-AZ/multi-DC redundancy** for Kafka/ClickHouse/Redis/app/serving with **per-component RTO/RPO** + multi-rack replication | `deploy/ha/` replication configs + `ops/dr/rto-rpo-matrix.md` | SCAFFOLD | Part 30.1; Part 9.3 (HA-DR replication) | Replication configs for each component; RTO/RPO matrix per component (e.g., audit-log RPO≈0, alerting RTO minutes); no SPOF; goes live with multi-DC fabric |
| **PLATFORM-26** | **Automated encrypted immutable backups** (audit log, model registry) + **restore tooling** + WORM/object-lock store wiring | `ops/backup/` + restore tooling + worm config | REAL | Part 30.1 (backup/restore); Part 19.3 (immutable audit) | Scheduled encrypted backup of Postgres/ClickHouse/audit/registry to object-lock bucket; restore tool reconstitutes and validates; backups immutable |
| **PLATFORM-27** | **DR failover runbooks** + scripted **restore-drill** (backup→teardown→restore→**validate row counts**→failover toggle→**drill report with RTO/RPO timings**) + chaos resilience injection | `ops/dr/runbooks/` + `scripts/dr-drill.sh` + drill-report generator | MOCK | Part 30.1 (restore/DR/cyber-resilience drills) | `dr-drill.sh` backs up, tears down, restores, asserts row counts match, toggles to standby, emits a drill report with measured RTO/RPO; runbook documents the rehearsed failover |
| **PLATFORM-28** | **BCP + graceful degradation**: board-approved **BCP doc (seeded approval)** + **real rules-only L1 fallback switch** | `governance/bcp.md` + `services/degradation-switch/` (real fallback to L1) | MOCK | Part 30.1 (BCP); Part 18 (rules-only fallback) | BCP doc (impact analysis/RTO-RPO/fallback) with seeded board-approval record; killing ML serving demonstrably drops the pipeline to L1-rules-only scoring (real switch, ties to PLATFORM-4) |
| **PLATFORM-29** | **SRE observability**: four golden signals per component, **OpenTelemetry tracing**, centralized structured logging (ClickHouse/OpenSearch), Prometheus+Grafana, **SLO/SLI + error budgets** | `observability/otel/` + Grafana dashboards + `observability/slo-definitions.yaml` | REAL | Part 30.2 | OTel collector traces event→feature→score→alert; Grafana dashboards show latency/traffic/errors/saturation per component; `slo-definitions.yaml` defines pipeline availability 99.9%, p99 scoring latency, alert freshness + error budgets |
| **PLATFORM-30** | **Operational alerting + incident management** (PagerDuty/Opsgenie routing, severity tiers, incident-commander role, runbooks, blameless post-mortems, RBI/CERT-In reporting) — scaffolded integration | `ops/oncall/` alert-routing config + `ops/incident-mgmt/` runbooks | SCAFFOLD | Part 30.2 (alerting/on-call/incident); Part 28.1 (CERT-In 6h) | Alertmanager routes to PagerDuty/Opsgenie by severity (scaffold endpoint); incident runbooks define severity levels, IC role, post-mortem template; RBI/CERT-In reporting step wired (scaffold to real channel) |
| **PLATFORM-31** | **Capacity management** + annual capacity-assessment artifact (**reviewed-by-ITSC** seeded record) | `ops/capacity/` assessment + forecast tool | REAL | Part 30.2 (capacity); Part 34.2 (forecasting) | Forecast tool projects capacity from growth inputs; annual assessment artifact generated with a seeded ITSC-review record |

### M5 — Governance, Regulatory & Org Artifacts (mocked) + Go-Live

| ID | What | Deliverable path | Status | Blueprint ref | Acceptance check |
|---|---|---|---|---|---|
| **PLATFORM-32** | **Governance DB schema + artifact-store service** (records keyed to model versions/releases, surfaced in dashboard governance view) | `governance/db/schema.sql` + `services/governance-api/` | REAL | Part 27.2 (inventory); Part 34 | Postgres governance schema (policies, committees, approvals, validations, vendors, DPIA, incidents, go-live ticks) keyed to model-version/release; FastAPI governance-api serves the records to the dashboard |
| **PLATFORM-33** | **SoD RBAC personas** (builder/labeler/actor/administrator) in Keycloak/JWT with **route-level enforcement** + segregation of training-data/label/build access | `governance/rbac/` keycloak roles + route guards + demo logins | MOCK | Part 19.3/19.6 (SoD); Part 27.2 | Four distinct Keycloak roles seeded; route guards enforce each persona can only perform its duty; demo logs in as each to show SoD (builder≠labeler≠actor≠admin) enforced in software |
| **PLATFORM-34** | **Mock model-governance & validation artifacts**: model-validation report + **simulated independent-validation sign-off gate** before prod promotion (seeded approval keyed to model version) | `governance/validation/` report generator + sign-off gate + seeded records | MOCK | Part 27.2 (independent validation); Part 22.4 (sign-off before prod) | Validation report (conceptual soundness/data/performance/stability/outcomes + LLM grounding/hallucination) with a simulated independent-validator sign-off block; promotion gate blocks "to Production" until sign-off record exists, keyed to model version |
| **PLATFORM-35** | **Mock FREE-AI / AI-governance bodies**: **AI/Model-Risk Committee** + **ethics committee** + board records (rosters, minutes, model-approval/incident-review/board-report rollups) + approval-queue/incident/board-pack software + **AI incident-reporting mechanism** | `governance/committees/` seeded records + `services/governance-api/` panels | MOCK | Part 27.2 (committee); Part 29.2 (ethics committee); Part 27.1 (incident form) | Committee rosters + minutes + model-approval decisions linked to model versions + incident reviews + board rollups seeded; approval-queue + incident-review + board-pack generator software; AI incident-reporting form (FREE-AI indicative form) wired |
| **PLATFORM-36** | **Mock policy/regulatory docs**: **board-approved AI Policy**, BCP (ref M4), **DPIA**/algorithmic-due-diligence, **DPO appointment + annual data-protection audit**, **lawful-basis/DPDP employee-monitoring mapping**, **breach-notification workflow** (CERT-In 6h / DPB / RBI), transparency/works-council/whistleblowing docs | `governance/docs/` generated md/pdf + seeded approval records | MOCK | Part 27.1; Part 28.1; Part 29.2; Part 19.6 | Each doc generated (md→pdf) with a seeded approval record (date/resolution id/signatories): AI Policy, DPIA, DPO record + audit report, lawful-basis map (DPDP closed legitimate-uses list), breach-notification workflow distinguishing personal-data breach vs cyber incident, transparency/whistleblowing/works-council notices |
| **PLATFORM-37** | **Human-in-the-loop natural-justice gate** (holds classification **pending human review** with proportionality/explanation) + DPIA sign-off binding | `services/hitl-gate/` + integration into scoring pipeline | MOCK | Part 19.6; Part 29.2; Part 15 (natural justice); Part 16 | Classifications enter `pending_review`; no fraud classification is acted on until a human approves (alert-only proven in software); proportionality + explanation shown; bound to DPIA sign-off record |
| **PLATFORM-38** | **Mock outsourcing/vendor-risk artifacts (AWS + NEAR AI)**: due-diligence, SLAs, exit strategy, concentration risk, **AI-specific clauses**, SBOM linkage | `governance/vendor-risk/` seeded vendor records + clause templates | MOCK | Part 32 (outsourcing); Part 34.4; Part 27.1 (AI clauses) | Vendor records for AWS + NEAR AI/Groq: DD questionnaire responses, SLA terms, exit strategy, concentration-risk assessment; AI-specific clause template (algorithmic bias/subcontractor AI/data confidentiality); SBOM (PLATFORM-17) linked to vendor register |
| **PLATFORM-39** | **Mock operating-model artifacts**: org chart, **Three-Lines RACI matrix**, committee charters, **RACI for key activities**, steering-committee/RAID/OKR, **FinOps** (tagging/showback/TCO), per-typology **investigation playbooks/SOPs**, **staffing-model calculator** (Erlang headcount/roster), **training/change-mgmt program + override-rate/alert-fatigue dashboard panel** | `governance/operating-model/` + `tools/staffing-calculator/` + `tools/finops/` + change-mgmt panel | MOCK | Part 33 (org/RACI/staffing/SOPs/adoption); Part 34.1/34.2 | Org chart + Three-Lines + committee charters; RACI for the 6 key activities (alert triage, block decision, model deploy, rule change, incident response, fairness review); RAID log + OKRs; FinOps tagging/showback/TCO; per-typology SOPs + KM wiki; staffing calculator derives headcount+roster from alert volume/handling-time/SLA; training curriculum + a real override-rate/alert-fatigue panel computed from dispositions |
| **PLATFORM-40** | **Documentation suite**: ADRs, runbooks/ops manuals, OpenAPI docs (index), data dictionary (stub/index), model-card index, SOPs, DR/BCP docs, **detection-coverage map**, **honest-limits statements**, **bibliography** | `docs/` consolidated documentation set | REAL | Part 34.3; Part 12 (coverage map + honest limits); Part 17.D (references) | ADR set; runbooks; OpenAPI + data-dictionary index links; model-card index; detection-coverage map (fraud vector→layer/lane) reproduced from Part 12; honest-limits statements verbatim-in-spirit; bibliography from Part 17.D |
| **PLATFORM-41** | **DB-backed go-live readiness checklist** aggregating status of ALL mocked artifacts (AI policy, DPO, DPIA, validation sign-off, VAPT, UAT, CAB, reporting-form, BCP, lawful-basis, staffing, vendor DD) + **threat-intel feedback loop** into rules/synthetic library | `governance/go-live/` checklist service + dashboard view + threat-intel feed | MOCK | Part 34.6 (go-live checklist); Part 34.5 (threat-intel); Part 13/19 (red-team cadence) | Checklist service reads each evidence record from the governance DB and renders a single go/no-go gate covering all Part 34.6 ticks (regulatory, security, reliability, quality, data, operating model, program); threat-intel feed routes new typologies back into rules + synthetic library (hand-off note to BACKEND/DATA) |

---

## 7. Detailed build instructions per milestone

> Spell-outs so nothing is lost. Where a number/list comes from the blueprint, it is authoritative — match it.

### M1 — Local Foundations

- **PLATFORM-1 (BOM + scaffolding).** Create `deploy/versions.bom.yaml` with **every** Part 24.3 pin (the table in §4). Establish the repo's `deploy/`, `infra/`, `observability/`, `security/`, `governance/`, `ops/`, `ci/`, `tools/`, `tests/` skeleton. Root `Makefile` targets: `up`, `down`, `core-up`, `app-up`, `topology-smoke`, `lint`, `test`, `tf-plan`, `sbom`, `scan`, `dr-drill`, `seed-governance`, `go-live`. Every downstream artifact references the BOM (no hardcoded versions elsewhere).
- **PLATFORM-2 (core compose).** `docker-compose.core.yml`: **Kafka** (KRaft or ZK, 1 broker dev, partitioned-by-entity note), **Flink** (jobmanager+taskmanager), **Redis** 7.4, **ClickHouse** 25 (8123/9000), **Postgres** 17 (5432), **MinIO** (9001 API / 9002 console), **Feast** sidecar, **schema-registry host** (Apicurio or Confluent — you host; DATA defines schemas, Part 28.2). Healthchecks on each. Ports must match CONTEXT.md §7; if you add any, update that table and log it. Root `docker-compose.yml` `include:`s core + app.
- **PLATFORM-3 (serving/app/identity/observability compose).** `docker-compose.app.yml`: **ONNX Runtime / Triton** serving (8001; ship a dummy model placeholder per §3 stub rules), **FastAPI app** (8000; stub→BACKEND image), **Keycloak** 25 (8080) with an exported `hawk-eye` realm (clients for frontend + services; the SoD roles come in PLATFORM-33), **MLflow** (5000; ML owns content), **Airflow** (orchestration), **Prometheus** (9090) + **Grafana** (3000) with provisioned datasources/dashboards.
- **PLATFORM-4 (reference topology + degradation switch).** Document the **Part 9.1 reference topology** exactly: Collectors/agents → Kafka → Flink (stateful enrichment + windowed features + CEP) → Redis/Feast + model-serving (ONNX/Triton; GPU for train/graph, CPU for inference) → Risk-fusion → alerts topic → Case/Alert store → ClickHouse (hot+cold, history, search, backfill) + audit/WORM → investigator dashboard; cross-cutting K8s/HSM/Prometheus/MLflow/Airflow/segmentation. Define the topic/stream names. Build `services/degradation-switch/`: a **real** toggle that, when ML serving is unhealthy, routes scoring to **L1-rules-only** (BACKEND's rules engine) and marks events for re-scoring — this is both the Part 18 continuity feature and the Part 30.1 BCP graceful-degradation. `make topology-smoke` pushes a synthetic L0 event through and asserts an alert lands.
- **PLATFORM-5 (sizing/cost calculator).** `tools/sizing/sizing_calculator.py`: inputs = transactions/day + telemetry multiplier (5–20× per Part 9.2). Outputs **Kafka** brokers (3–5, RF 3, entity-partitioned), **Flink** task managers (by keyed-state + rate), **ClickHouse** shards (sharded+replicated, hot-cold, ~10–20× compression), **GPU** pool (small, train/graph only), **Redis** (active-population features). AWS cost model uses Part 26.3 instances: `m6i.large/xlarge`, `r6i.xlarge`, ElastiCache node, `g5.xlarge`, small RDS, S3 → monthly $ estimate. Unit-test the formulas.
- **PLATFORM-6 (compute-placement profiles, SCAFFOLD).** `deploy/profiles/compute-placement.yaml`: trees train on **CPU**; sequence/graph nets train on **GPU**; **inference is CPU** (trees + small nets via ONNX); AWS pilot uses **g5/p4d** for training + CPU instances for serving; on-prem = GPU pool + CPU inference (Part 9.1, 22.5). ADR records the placement rationale. SCAFFOLD because it needs real GPU hardware/quota to run.

### M2 — IaC, Networking, Zero-Trust & Secrets

- **PLATFORM-7 (Terraform aws|onprem, SCAFFOLD).** `infra/terraform/` with a root variable `target = "aws" | "onprem"`. **AWS modules** (Part 26.1): MSK; Managed Service for Apache Flink; ElastiCache-Redis; EC2 (ClickHouse on gp3, ONNX/Triton serving, Keycloak); RDS-Postgres; S3 (SSE-KMS, versioned, **object-lock**); MWAA; ALB; Secrets Manager/SSM (holding `NEAR_AI_API_KEY`,`GROQ_API_KEY`,`PII_HMAC_KEY`); KMS. **on-prem modules** mirror them (Kafka/Flink/Redis/Postgres/MinIO/Airflow/Vault/HSM/Keycloak). `envs/aws` and `envs/onprem` both `terraform validate` + `plan` (use a null/mock backend so no creds needed). **No `apply`.** SCAFFOLD: real AWS account makes it live.
- **PLATFORM-8 (migration map + Lightsail ADR).** `migration-map.md`: the 8 swaps (`MSK→Kafka`, `Managed Flink→Flink`, `ElastiCache→Redis`, `RDS→Postgres`, `S3→MinIO`, `KMS→HSM`, `Secrets Manager→Vault`, `MWAA→Airflow`) **plus** the LLM swap (external NEAR AI → on-prem **H100/H200 in Intel TDX** running **gpt-oss-120b**, OpenAI-compatible, same attestation). `ADR-0001-ec2-in-vpc.md`: decide **EC2-in-VPC** over Lightsail for the realistic pilot (Lightsail = pure demo only), with a comparison matrix. REAL (docs/ADR).
- **PLATFORM-9 (K8s/Helm on-prem, SCAFFOLD).** Helm charts for all core+app services for scale/HA/rolling deploys. Every workload carries a **data-residency `in-india` / region label** (Part 9.3, Part 16 localization). Add an OPA/Conftest **residency-assertion** policy that fails if any workload lacks the label or pins a non-India region. SCAFFOLD: needs a real cluster.
- **PLATFORM-10 (zero-trust network, SCAFFOLD).** `modules/network/`: VPC with **private subnets** for data/compute, **ALB-only public subnet**, least-open **SG + NACL**. **NAT gateway egress allow-list = NEAR AI (`cloud-api.near.ai`) + Groq (`api.groq.com`) endpoints ONLY**; everything else **no internet egress** (Part 26.2, Part 19.3 air-gap). `zero-trust-policy.md` maps each tier to a security zone with micro-segmentation and zero-trust between components.
- **PLATFORM-11 (IAM + mTLS/SPIFFE, SCAFFOLD).** `modules/iam/`: least-privilege roles, **no long-lived keys**. `deploy/mtls/`: SPIFFE/SPIRE identities + mTLS certs per service; **least-privilege service accounts; no shared/anonymous accounts** (Part 19.3 — the exact anti-pattern the system catches).
- **PLATFORM-12 (secrets + KMS, SCAFFOLD).** Vault dev (or Secrets Manager/SSM) holds `NEAR_AI_API_KEY`, `GROQ_API_KEY`, `PII_HMAC_KEY`. `modules/kms/` wires SSE-KMS at rest. The `PII_HMAC_KEY` is **exposed by secret reference** to BACKEND's tokenizer (Part 25.3) — never hardcoded, never in git. Field-level PII key handling integrated.
- **PLATFORM-13 (mock HSM, MOCK).** SoftHSM2 PKCS#11 token; a key-custody wrapper that signs/encrypts via PKCS#11 for dev. Doc: "**SoftHSM is dev-only, not a real HSM**; production swaps a physical/cloud HSM" (Part 9.3/19.3).
- **PLATFORM-14 (mock TEE attestation, MOCK).** `services/tee-attestation/`: `POST /attest` issues a **dual quote** (simulated **Intel TDX CPU + NVIDIA H200 GPU**) per request, signed with a **local key**; `POST /verify` validates the quote (pass/fail). An **enclave-mode flag** simulates "TLS terminates inside the enclave". Assert **PII tokenized before egress**. `deploy/profiles/onprem-llm-node.yaml`: H100/H200 + TDX + gpt-oss-120b OpenAI-compatible profile (Part 26.4). Demo: request → quote → verify → audit-memo fields (`provider`, `tee_attested`, `attestation_id`, `model`, `prompt_hash`, `ts`). MOCK: no real confidential-compute hardware exists here.
- **PLATFORM-15 (mock PAM shim, MOCK).** `services/pam-shim/`: records a simulated privileged-admin session (who/when/what + a "session recording" stub) and enforces least-privilege for platform admins. `admin-access-policy.md`: real PAM (CyberArk/BeyondTrust) swap. Ties to PLATFORM-33 SoD personas.

### M3 — CI/CD, Security Testing & Supply-Chain

- **PLATFORM-16 (CI pipeline, REAL).** `.github/workflows/ci.yml` stages in order (Part 31.2): **lint** (ruff/black/mypy for Python platform code; eslint/tsc/prettier for the UAT harness) → **unit** → **integration** → **contract** (API schema) → **data-validation** (invoke DATA's Great-Expectations/Pandera gate) → **ML behavioral/fairness** (invoke ML's `tests/ml/` gate) → **security scans** (PLATFORM-17) → **build + sign** artifacts/images. Each gate fails the build on regression. Provide the **test-pyramid harness** in `tests/` so each laptop plugs its unit/contract tests in.
- **PLATFORM-17 (supply-chain/DevSecOps, SCAFFOLD).** `ci/security/` stages: **Syft** SBOM in **SPDX + CycloneDX** (Part 34.4 CERT-In v2.0); **Grype + Trivy** CVE + container scan; **Semgrep** SAST + **OWASP ZAP** DAST + IAST hook; **gitleaks/trufflehog** secrets scan; **Conftest/tfsec** IaC scan; **cosign** model-signature verify on load. **Pinned deps from an internal artifact mirror** (egress-off patching path, Part 19.4/19.5) — config present but the real bank mirror makes it live ⇒ SCAFFOLD.
- **PLATFORM-18 (CD pipeline, REAL).** `deploy/argocd/` GitOps app manifests; `.github/workflows/cd.yml` does **blue-green/canary** with **auto-rollback on SLO/metric regression** and **feature flags**. Three env overlays: **dev → staging (prod-like, masked data) → production**, parity via shared IaC (Part 31.2). Model CD path = shadow→champion/challenger→canary with signature verify on load (defer model logic to ML; you provide the deploy mechanics).
- **PLATFORM-19 (release + change governance, SCAFFOLD).** `tools/release/`: cut versioned releases + release notes + a **requirement→code→test→deploy traceability** matrix. `governance/change-mgmt/`: change-request workflow, risk-assessment form, **scheduled-window enforcement**, documented **rollback runbook** (Part 31.3, Part 34.3). CAB approval is the human step ⇒ SCAFFOLD.
- **PLATFORM-20 (threat model + framework mapping, REAL).** `security/threat-model.md`: STRIDE across the platform + the **three attacker classes** (external breach, malicious insider, the monitored subjects evading) + insider lens (Part 19.1). `security/framework-mapping.md`: the **ML-attack→mitigation table** mapped to **MITRE ATLAS** — evasion (peer-relative baselines, hide thresholds, randomized sampling, diverse ensemble, adversarial testing), poisoning (segregate touch-train-data/label/build, provenance/lineage, anomaly-check trainset, peer-anchored+change-point baselines, label-distribution review, immutable label audit), inversion/membership (internal-only authenticated rate-limited inference, no raw scores, DP/regularization, extraction-pattern monitoring), extraction/theft (encrypted+signed+access-controlled artifacts, no model leaves perimeter, registry access logging), explanation manipulation (don't rely solely on post-hoc; prefer interpretable + rule provenance; cross-check), supply-chain AML.T0048 (SBOM/CVE/container scan/model signing/internal mirror). Plus **OWASP ML Top 10 / OWASP Top 10, NIST AI RMF, NIST CSF, RBI cyber directions** alignment. Plus the **FREE-AI 7 Sutras → control** map (Trust, People First, Innovation, Fairness→Part 29, Accountability→immutable audit+HITL, Explainability→Parts 20.6+25, Resilience→Part 30).
- **PLATFORM-21 (perf/chaos/security suites + SIEM rules, REAL).** `tests/perf/`: k6/Locust **sustained + burst** at target TPS, **p99 latency budget** assertion, **soak** test (Part 31.1). `tests/chaos/`: kill a **Kafka broker** and a **serving node**; assert pipeline survives (degradation kicks in) (Part 30.1). `tests/security/`: SAST/DAST/IAST + dependency/CVE + ATLAS adversarial-ML red-team hooks. `security/siem/detection-rules/`: detect **extraction-pattern querying, abnormal label edits, training-data anomalies, config/threshold changes** (Part 19.5) — the detection platform watched like any crown-jewel asset.
- **PLATFORM-22 (vuln-management programme, REAL).** `security/vuln-mgmt/`: continuous scanning of OS/containers/deps/ML-artifacts; **risk-ranked remediation** with **patch SLAs** (critical ≤7d), scheduled patch windows + **emergency-patch path**; egress-off internal-mirror patching note; **adversarial-ML re-test as a recurring control**. Tracker view ingests Grype/Trivy output and lists findings ranked with remediation status (Part 19.5).
- **PLATFORM-23 (mock VAPT/red-team/model-risk, MOCK).** `security/reports/vapt.md` (scope/methodology/CVSS-scored findings/remediation/retest sign-off — Part 19.4/31.1); `redteam.md` (ATLAS evasion/poisoning/inversion/extraction probes against deployed models); `model-risk.md` (periodic model-risk review tied to a model version — Part 13). Seed these into the PLATFORM-22 tracker so the program shows a **"VAPT passed"** state.
- **PLATFORM-24 (mock investigator UAT, MOCK).** `tests/uat/investigator_uat.spec.ts` (Playwright): drive the dashboard end-to-end — **triage → entity-360 → explanation → case disposition** — asserting each step (Part 31.1). Emit a **signed-off UAT report** (pass/fail per test case) as the acceptance artifact. Drives the real FRONTEND when present; otherwise a stub.

### M4 — HA/DR/BCP & SRE Observability

- **PLATFORM-25 (HA redundancy + RTO/RPO, SCAFFOLD).** `deploy/ha/` replication configs for Kafka/ClickHouse/Redis/app/serving, **multi-AZ (AWS) / multi-DC (on-prem), multi-rack** (Part 30.1, 9.3). `ops/dr/rto-rpo-matrix.md`: per-component RTO/RPO (audit-log RPO≈0, alerting RTO minutes), no SPOF. SCAFFOLD: needs real multi-DC fabric.
- **PLATFORM-26 (immutable backups + restore, REAL).** `ops/backup/`: automated, **encrypted, immutable** backups of the **audit log and model registry** (and Postgres/ClickHouse) to **object-lock/WORM** buckets; restore tooling that reconstitutes and validates (Part 30.1). Coordinate with DATABASE who owns the WORM store; you own the backup/restore orchestration.
- **PLATFORM-27 (DR runbooks + restore-drill, MOCK).** `ops/dr/runbooks/` documented, rehearsable failover; `scripts/dr-drill.sh`: back up Postgres/ClickHouse → tear down → restore from snapshot/object-store → **validate row counts** → toggle failover to standby → emit a **drill report with measured RTO/RPO**. Chaos resilience injection. MOCK because the *drill* is an org act; the script + report are real evidence.
- **PLATFORM-28 (BCP + degradation, MOCK).** `governance/bcp.md`: board-approved BCP (impact analysis, RTO/RPO, fallback procedures) with a **seeded board-approval record**. `services/degradation-switch/` is the **real** rules-only L1 fallback (shared with PLATFORM-4): killing ML serving demonstrably keeps L1-rules scoring alive (Part 30.1, Part 18).
- **PLATFORM-29 (SRE observability, REAL).** `observability/otel/`: OpenTelemetry collector tracing the **event→feature→score→alert** path. Grafana dashboards: the **four golden signals** (latency, traffic, errors, saturation) per component. Centralized **structured logging** (distinct from the immutable audit log) into ClickHouse/OpenSearch. `observability/slo-definitions.yaml`: **alert-pipeline availability 99.9%, p99 scoring latency, alert-delivery freshness** + **error budgets** that gate change velocity (Part 30.2).
- **PLATFORM-30 (alerting + incident mgmt, SCAFFOLD).** `ops/oncall/`: Alertmanager routes pipeline-lag/drift/node-down to a **PagerDuty/Opsgenie on-call rotation** with **severity tiers** (scaffold endpoint). `ops/incident-mgmt/runbooks/`: severity levels, **incident-commander** role, runbooks, **blameless post-mortem** template, **RBI/CERT-In incident reporting** step (Part 30.2; CERT-In 6h Part 28.1).
- **PLATFORM-31 (capacity management, REAL).** `ops/capacity/`: forecast tool projecting capacity from growth inputs; **annual capacity-assessment** artifact with a **seeded ITSC-review record** (Part 30.2, Part 34.2).

### M5 — Governance, Regulatory & Org Artifacts (mocked) + Go-Live

> These are the **24 governance MOCKS**. Each generated doc gets a **seeded approval/evidence record** in the governance DB (PLATFORM-32), keyed where relevant to a model version or release, and is surfaced in the dashboard governance view (FRONTEND renders; you serve via governance-api). Build the **process**, not the human/legal act.

- **PLATFORM-32 (governance DB + artifact-store, REAL).** `governance/db/schema.sql`: tables for **policies, committees + members + minutes, approvals/sign-offs, model-validation reports, vendors + clauses, DPIA, incidents, go-live ticks, training/override metrics, staffing plans**, each keyed to model-version/release where relevant. `services/governance-api/` (FastAPI) serves them to the dashboard governance view.
- **PLATFORM-33 (SoD RBAC personas, MOCK).** Seed **builder / labeler / actor / administrator** roles in Keycloak/JWT; route-level guards enforce **who-touches-training-data ≠ who-labels ≠ who-builds ≠ who-administers** (Part 19.3/19.6, Part 27.2). Demo logins per persona prove SoD in software.
- **PLATFORM-34 (model-validation + sign-off gate, MOCK).** `governance/validation/`: a **model-validation report** generator (conceptual soundness, data quality, performance/stability, outcomes; LLM gateway validated for **grounding/hallucination** not just accuracy — Part 27.2). A **simulated independent-validation sign-off gate** that **blocks promotion to Production** until a seeded sign-off record (keyed to model version) exists (Part 22.4). The real act needs a real independent validator ⇒ MOCK.
- **PLATFORM-35 (FREE-AI/AI-governance bodies, MOCK).** `governance/committees/`: seed **AI/Model-Risk Committee** (risk, compliance, business, tech) + **AI ethics committee** + board records — rosters, minutes, **model-approval decisions linked to model versions**, incident reviews, board-report rollups. Software: **approval queue**, **incident-review** view, **board/SCBMF-pack generator**, and the **AI incident-reporting mechanism** (FREE-AI indicative form). Part 27.1/27.2, Part 29.2.
- **PLATFORM-36 (policy/regulatory docs, MOCK).** Generate (md→pdf) with seeded approval records: **Board-approved AI Policy** (scope/principles/roles/risk tiers, FREE-AI 6 pillars + 7 Sutras), **DPIA**/algorithmic-due-diligence (incl. the **employee-monitoring** DPIA), **DPO appointment** record (India-resident) + **annual independent data-protection audit** report, **lawful-basis mapping** against DPDP's **closed "legitimate uses" list**, **breach-notification workflow** to **Data Protection Board + affected principals + CERT-In 6-hour + RBI** (distinguishing personal-data breach vs general cyber incident), **transparency/works-council/whistleblowing** notices. Part 27.1, 28.1, 29.2, 19.6.
- **PLATFORM-37 (HITL natural-justice gate, MOCK).** `services/hitl-gate/`: holds any classification in **`pending_review`**; **no fraud classification is acted on until a human approves** (this is the software proof of **alert-only + natural justice**, SBI v. Rajesh Agarwal — Part 15, 16, 19.6, 29.2). Shows proportionality + explanation; bound to the DPIA sign-off record. Integrates into the scoring pipeline (coordinate the hook with BACKEND).
- **PLATFORM-38 (vendor/outsourcing risk, MOCK).** `governance/vendor-risk/`: for **AWS + NEAR AI/Groq** — due-diligence questionnaire responses, SLA terms, **exit strategy**, **concentration-risk** assessment (RBI Outsourcing 2023), **AI-specific clauses** (algorithmic bias, subcontractor AI use, data confidentiality/localization, audit rights — FREE-AI), **SBOM linkage** (from PLATFORM-17). Seed as vendor records in the outsourcing register. Part 32, 34.4, 27.1.
- **PLATFORM-39 (operating-model artifacts, MOCK).** `governance/operating-model/`: **org chart** + **Three-Lines-of-Defense** + committee charters (AI/Model-Risk, ISC, ITSC, Audit); the **RACI for key activities** (alert triage & EDD; block decision; model deploy; rule/threshold change; incident response; fairness review — reproduce Part 33.2 R/A/C/I rows); steering committee + **RAID log** + **OKRs**; **FinOps** (cost monitoring, resource tagging, showback/chargeback, TCO/build-vs-buy, capacity & cost forecasting — Part 34.2); per-typology **investigation playbooks/SOPs** + standardized EDD steps + evidence collection + **handoff to HR/CBI/ED** + living KM wiki (Part 33.3); `tools/staffing-calculator/` deriving **headcount + shift roster** from alert volume, handling-time, SLA (Erlang/throughput — Part 33.3); **training/change-mgmt program** (curriculum, DPDP/security modules) + a **real override-rate (trust calibration) + alert-fatigue dashboard panel** computed from disposition/feedback data (Part 33.4).
- **PLATFORM-40 (documentation suite, REAL).** `docs/`: **ADRs**, **runbooks/ops manuals**, **OpenAPI** index, **data dictionary** index, **model-card** index, **SOPs/playbooks**, **DR/BCP** docs, the **detection-coverage map** (reproduce Part 12: fraud vector → caught-by layer → key signals → lane), the **honest-limits statements** (credit fraud slow-only; executive override partial; low-and-slow mitigated not eliminated — Part 12), and the **bibliography** (Part 17.D). Part 34.3.
- **PLATFORM-41 (go-live readiness checklist, MOCK).** `governance/go-live/`: a **DB-backed checklist service** that reads each evidence record and renders one **go/no-go gate** covering **all Part 34.6 ticks** — Regulatory & governance (board AI policy, model inventory+tiering+independent validation, DPO/DPIA/lawful-basis/cross-border, fairness audit, RBI ITGRCA controls, AI incident-reporting + CERT-In/RBI wired), Security (threat model+STRIDE/ATLAS, VAPT+adversarial red-team, PAM/least-privilege/immutable audit, SBOM+CVE clean, secrets-in-vault/keys-in-HSM/PII-tokenization), Reliability (RTO/RPO+DR drill, backups+restore drill, SLOs/on-call/runbooks, chaos, graceful degradation), Quality (ML behavioral/metamorphic/fairness green, load/p99 met, UAT signed, CAB live), Data & integration (sources onboarded+reconciled+lineage, DQ SLAs+schema registry, retention/erasure), Operating model (team staffed/trained, escalation+SOPs, RACI, feedback loop), Program (steering+RAID+OKRs, vendor DD+exit, docs/ADRs/model cards). Plus the **threat-intel feedback loop** routing new typologies back into rules + the synthetic library (hand-off note tagging BACKEND/DATA — Part 34.5).

---

## 8. Testing & all checks (commands + what must pass)

Provide a single `make` entrypoint per check. **Definition of a passing build:** all of the below green.

**Project / lint / format / type:**
- Python (platform services, tools): `ruff check .`, `black --check .`, `mypy .` — clean.
- TS (UAT harness): `eslint . && tsc --noEmit && prettier --check .` — clean.
- `terraform fmt -check` + `terraform validate` (both `envs/aws` and `envs/onprem`).
- `helm lint` + `conftest test` (residency + zero-trust policies).
- `docker compose config` validates all compose files.

**Dependency pinning:** verify every running version equals the Part 24.3 pin in `deploy/versions.bom.yaml`; CI fails on drift.

**Unit + integration + contract:**
- `make test` runs platform unit tests (sizing calculator, staffing calculator, governance-api, tee-attestation issuer/verifier, degradation switch, hitl-gate).
- Integration: `make topology-smoke` flows a synthetic L0 event end-to-end and asserts an alert.
- Contract: API-schema contract tests against `BACKEND.md` route table (governance-api routes you own).

**Domain-specific checks (you own the harness; invoke the owners' gates):**
- **ML behavioral/metamorphic/fairness/leakage tests** — CI invokes `tests/ml/` (ML laptop owns content); your job is the gate wiring + fail-on-regression.
- **Data validation** — CI invokes DATA's Great-Expectations/Pandera gate.
- **Security scans** — `make scan`: Syft SBOM (SPDX+CycloneDX), Grype/Trivy CVE+container, Semgrep SAST, ZAP DAST, gitleaks secrets, Conftest/tfsec IaC, cosign signature verify. No critical findings unremediated.
- **Adversarial-ML red-team** — `tests/security/` ATLAS hooks runnable; PLATFORM-23 report seeded.

**Performance / latency budgets:** `make perf` (k6/Locust) — sustained + burst at target TPS, **p99 scoring-latency budget met**, soak stable. Tie thresholds to the SLOs in `slo-definitions.yaml`.

**Chaos / resilience:** `make chaos` kills a broker + serving node; pipeline survives via degradation; `make dr-drill` runs the restore drill and produces an RTO/RPO report.

**Governance / go-live:** `make seed-governance` seeds all 24 mocks; `make go-live` renders the readiness checklist and shows the go/no-go gate.

---

## 9. Blueprint validation gate

A task is **done only when its blueprint requirement is met**. For each milestone, confirm in `docs/laptops/06-platform.md`: task ID → Part → how verified. Map of what you own → covered:

- **Part 8 / 17.C (tech stack)** → PLATFORM-1, 2, 3 (Kafka→Flink→Feast/Redis→Python→ONNX/Triton→ClickHouse→React; Rust gateways hosted).
- **Part 9.1 (reference topology) / 9.2 (sizing) / 9.3 (security/residency/HA-DR/integration)** → PLATFORM-4, 5, 9, 10, 11, 12, 13, 25, 26.
- **Part 12 (coverage map + honest limits)** → PLATFORM-40.
- **Part 13 / 15 (model-risk reviews, natural justice, works-council)** → PLATFORM-23, 36, 37.
- **Part 16 (RBI/DPDP compliance, localization)** → PLATFORM-9, 36, 37, 41.
- **Part 19 (STRIDE/ATLAS, ML-attack mitigations, infra security, supply-chain, vuln-mgmt, governance/privacy, framework alignment)** → PLATFORM-10, 11, 12, 13, 15, 17, 20, 21, 22, 23, 33.
- **Part 24.3 (version BOM)** → PLATFORM-1 (+ enforced in CI).
- **Part 25.2/25.3/25.4 (TEE + attestation + tokenize-before-egress)** → PLATFORM-14, 12, 10.
- **Part 26 (AWS pilot ap-south-1 + security + sizing + migration + on-prem LLM node)** → PLATFORM-7, 8, 10, 14, 5.
- **Part 26.2 (AWS security: WAF + GuardDuty + Security Hub + Inspector + CloudTrail, NAT egress allow-list, IAM least-priv, KMS, mTLS)** → PLATFORM-7 (WAF/GuardDuty/SecurityHub/Inspector/CloudTrail modules), PLATFORM-10 (NAT egress allow-list), PLATFORM-11 (IAM), PLATFORM-12 (KMS); Inspector findings → PLATFORM-22 tracker; CloudTrail → audit.
- **Part 27 (MRM + FREE-AI)** → PLATFORM-32, 34, 35, 36.
- **Part 28 (data governance + DPDP)** → PLATFORM-36 (+ DATA owns catalog/quality/lineage; you own DPIA/DPO/breach/lawful-basis/cross-border).
- **Part 29 (fairness program + ethics committee + transparency)** → PLATFORM-35, 36, 37 (ML owns the fairness TEST code).
- **Part 30 (HA/DR/BCP/SRE/chaos/incident/capacity)** → PLATFORM-25, 26, 27, 28, 29, 30, 31.
- **Part 31 (test strategy + CI/CD + change mgmt)** → PLATFORM-16, 17, 18, 19, 21, 24.
- **Part 32 (integration runtime: api-gateway, schema-registry, reliability, outsourcing)** → PLATFORM-2 (schema-registry host), 38 (host api-gateway via BACKEND-28 seam), reliability infra in topology.
- **Part 33 (operating model/RACI/staffing/SOPs/adoption)** → PLATFORM-39.
- **Part 34 (program governance/FinOps/vendor risk/docs/threat-intel/go-live)** → PLATFORM-19, 38, 39, 40, 41.

**Must-cover capability self-check (all present above):** docker-compose walking skeleton + service map/ports/env/secrets (PLATFORM-1/2/3, CONTEXT.md §7); K8s manifests (PLATFORM-9); Terraform AWS+on-prem (PLATFORM-7, target=aws|onprem); security network/zero-trust/mTLS, secrets vault, KMS/HSM mock, PAM mock, field encryption (PLATFORM-10/11/12/13/15); adversarial-ML defenses + ATLAS map (PLATFORM-20); supply-chain/DevSecOps SBOM/CVE/dep/container scan/model signing/SAST-DAST-IAST (PLATFORM-17); vuln-management (PLATFORM-22); TEE-attestation mock (PLATFORM-14); observability Prom/Grafana/OTel/SLOs/golden-signals (PLATFORM-29); HA/DR/BCP + chaos + restore-drill (PLATFORM-25/26/27/28); CI/CD GitOps blue-green/canary + change mgmt (PLATFORM-16/18/19); cross-workstream integration-test harness (PLATFORM-16/21, tests/); and the **24 governance mocks** (board AI policy PLATFORM-36, model-risk committee PLATFORM-35, independent-validation report PLATFORM-34, DPO/DPIA PLATFORM-36, fairness/ethics committee PLATFORM-35, operating-model/RACI PLATFORM-39, vendor due-diligence PLATFORM-38, simulated investigator UAT PLATFORM-24, go-live readiness checklist PLATFORM-41, plus SoD personas PLATFORM-33, HITL gate PLATFORM-37, BCP PLATFORM-28, VAPT/red-team PLATFORM-23, breach-notification/lawful-basis/transparency PLATFORM-36, FinOps/staffing/training PLATFORM-39).

---

## 10. Definition of Done & handoff

**Per-milestone DoD:**
- **M1 done when:** `docker compose up` brings the full core+app stack healthy; ports match CONTEXT.md §7; `make topology-smoke` flows a synthetic event to an alert; degradation switch falls back to L1-rules-only; sizing calculator + compute-placement profiles exist; BOM enforced.
- **M2 done when:** `terraform plan` succeeds for both `envs/aws` and `envs/onprem`; migration map + EC2-in-VPC ADR written; Helm renders with residency labels (Conftest passes); zero-trust network + egress allow-list (NEAR AI/Groq only) defined; IAM/mTLS/SPIFFE + secrets/KMS wired; mock HSM + mock TEE attestation (dual quote issue→verify) + mock PAM shim run.
- **M3 done when:** CI runs the full pyramid + ML/data/security gates and goes green; SBOM (SPDX+CycloneDX) + CVE/container/SAST/DAST/secrets/IaC scans + cosign verify present; CD does blue-green/canary with rollback + 3-env parity; release/change governance tooling exists; threat model + ATLAS map + framework alignment + 7-Sutra map written; perf/chaos/SIEM suites pass; vuln tracker live; mock VAPT/red-team + UAT artifacts seeded.
- **M4 done when:** HA configs + RTO/RPO matrix exist; immutable backups + restore tooling work; `dr-drill.sh` produces an RTO/RPO drill report; BCP doc + seeded approval + real rules-only fallback verified; OTel tracing + golden-signal Grafana dashboards + SLO/error-budget definitions live; alerting/on-call/incident runbooks + capacity assessment present.
- **M5 done when:** governance DB + governance-api serve all records; all **24 mocks** seeded with approval/evidence records keyed to model versions/releases; SoD personas enforce in software; independent-validation sign-off gate blocks prod promotion; HITL gate holds classifications pending human review (alert-only proven); `make go-live` renders the readiness checklist go/no-go covering every Part 34.6 tick; documentation suite + detection-coverage map + honest-limits + bibliography complete.

**Every milestone, before you close it:**
1. Update **`TODO.md` §6** rows (`[x]` only when blueprint-validated).
2. Append cross-cutting decisions/interfaces/ports to **`CONTEXT.md`** (newest first); update the §7 ports table.
3. Record validations, files, deviations, blockers in **`docs/laptops/06-platform.md`**.
4. **Do NOT edit `BACKEND.md`** — propose contract changes in CONTEXT.md tagging `[BACKEND]`.
5. Open a PR to `main` from `hawk-eye/platform`.

**Integration test with other parts (final handoff):**
- Run the **cross-workstream integration harness** (`tests/`): bring up the full compose stack, push a synthetic fraud burst (the `create_beneficiary → approve_payment` scenario from DATA), confirm it flows L0→L1→L2→…→L6→alert→dashboard, the **HITL gate holds it pending human review**, an investigator disposition writes a label (EDD loop), and the **go-live checklist** reflects green evidence. Use stubs for any laptop not yet merged, clearly labelled.
- Confirm the **degradation switch** keeps the pipeline alive (L1-rules-only) when ML serving is killed — proving the BCP continuity feature and the alert-only golden rule.

> Restate the golden rules before you ship each milestone: **ALERT-ONLY · ON-PREM + SYNTHETIC · VALIDATE-AGAINST-BLUEPRINT · NOTHING-DROPPED · STAY-IN-LANE.**
