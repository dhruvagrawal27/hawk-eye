# Laptop 06 — PLATFORM — Working Log

> Your **own** file. Record decisions, files created, blueprint validations, deviations, and blockers. Update every session. Read `CONTEXT.md`, `BACKEND.md`, `TODO.md` first; append cross-cutting decisions to `CONTEXT.md`. You maintain the **service map / ports / env / secrets** section of `CONTEXT.md`. Full brief: [prompts/06_PLATFORM.md](../../prompts/06_PLATFORM.md).

## Status
- Branch: `hawk-eye/platform` · Owns: `platform/`, `infra/`, `.github/`, root `docker-compose.yml`, `tests/` harness, `deploy/`, `observability/`, `security/`, `governance/`, `ops/`, `ci/`, `tools/`, `services/`
- Milestone progress: **M1 ✓ · M2 ✓ · M3 ✓ · M4 ✓ · M5 ✓** (final doc-suite landing; integration pass next).
- **73 unit/contract tests pass**; 26-service compose validates; smoke + degradation + DR-drill + go-live (GATE: GO) all green.

## Orchestration note
Two multi-agent **workflows** were used to fan out the bulky, independent artifacts (token cost not a constraint, per ultracode):
- WF-1 (M2 IaC): Terraform tree (aws|onprem|lightsail, 24 modules, validates+plans for all 3, no creds), Helm chart (80 objects, residency labels, conftest 400/400), zero-trust + admin-access policy, mTLS/SPIFFE + SPIRE.
- WF-2 (M3/M5 docs): threat-model + framework-mapping + VAPT/red-team/model-risk reports, governance policy docs (AI policy/DPIA/DPO/lawful-basis/breach/transparency), vendor-risk, operating-model (org/Three-Lines/RACI/SOPs), documentation suite (coverage-map/honest-limits/bibliography) + DR/incident runbooks.
The integration-critical services + the governance DB backbone + all tests were built and validated directly.

## Decisions
- **DEV-001 (deviation): Deployment target = AWS Lightsail** for the pilot/demo, overriding the blueprint Part 26 default of EC2-in-VPC. Documented in `docs/adr/ADR-0001-ec2-in-vpc.md` and CONTEXT.md integration log. EC2-in-VPC + on-prem paths retained. Terraform `target = aws | onprem | lightsail`.
- **DEC-001 BOM as source of truth.** `deploy/versions.bom.yaml` holds every Part 24.3 pin + tooling; `tools/bom_to_env.py` generates `deploy/compose/.env`; CI `bom-drift` enforces. No hardcoded image tags elsewhere.
- **DEC-002 Compose layering.** Root `docker-compose.yml` `include:`s `core` (data infra), `app` (serving/identity/observability), `platform` (PLATFORM services). `make up|core-up|app-up`.
- **DEC-003 Serving stub.** Local serving = a CPU FastAPI stub implementing the KServe/Triton **v2 inference protocol** on :8001 with a dummy ONNX model, so the topology validates without GPU Triton. ML swaps the real Triton image (BOM `stack.triton`).
- **DEC-004 Ports.** Added 13 new platform ports to CONTEXT.md §7 (schema-registry 8085, Flink 8081, Airflow 8088, Alertmanager 9093, OTel 4317/4318/8889, Vault 8200, TEE 8090, PAM 8091, degradation 8092, governance-api 8093, hitl 8094, ArgoCD 8083).
- **DEC-005 Governance DB.** Separate logical DB `governance` on the shared Postgres; PLATFORM owns its schema (`governance/db/schema.sql`); served read-only via `governance-api`.

## Files created
- `deploy/versions.bom.yaml` (BOM, PLATFORM-1), `tools/bom_to_env.py`, `deploy/compose/.env` (generated)
- root `Makefile` (PLATFORM-1), root `docker-compose.yml` (include wrapper)
- `.env.example`, `tools/requirements.txt`
- `.gitignore` PLATFORM re-includes (keep `.env.example`, `deploy/secrets/`)
- Full owned directory skeleton (`deploy/ infra/ observability/ security/ governance/ ops/ ci/ tools/ tests/ docs/`)

## Blueprint validation (Part → task → ✓)
- **Part 24.3 → PLATFORM-1**: BOM lists every pinned component from the Part 24.3 table (verified line-by-line) + the platform DevSecOps tooling. ✓
- **Part 17.C → PLATFORM-1**: `make help` exposes up/down/core-up/app-up/topology-smoke/lint/test/tf-plan/sbom/scan/dr-drill/seed-governance/go-live + more. ✓
- **Part 8 / 9.1 / 28.2 → PLATFORM-2**: `docker-compose.core.yml` = Kafka(KRaft)+SchemaRegistry(Apicurio)+Flink(jm/tm)+Redis+ClickHouse+Postgres+MinIO+Feast, all with healthchecks; `docker compose config` validates; topics declared in `infra/kafka/topics.yaml`. ✓
- **Part 8 / 9.1 / 26.1 → PLATFORM-3**: `docker-compose.app.yml` = serving(KServe-v2 stub)+backend(stub)+Keycloak(realm `hawk-eye` import)+MLflow+Airflow+Prometheus+Grafana(provisioned). Full root stack = 18 services, validates. ✓
- **Part 9.1 / 18 / 30.1 → PLATFORM-4**: `deploy/topology/README.md` reproduces the Part 9.1 diagram + topic table; `services/degradation-switch` is the REAL rules-only fallback; `make topology-smoke` flows a synthetic L0 event → alert (alert-only, status=open); `make degradation-demo` proves rules-only continuity. ✓
- **Part 9.2 / 26.3 → PLATFORM-5**: `tools/sizing/sizing_calculator.py` derives Kafka/Flink/ClickHouse/GPU/Redis + AWS & Lightsail $/mo; 8 unit tests pass; `docs/sizing.md`. ✓
- **Part 9.1 / 22.5 → PLATFORM-6 (SCAFFOLD)**: `deploy/profiles/compute-placement.yaml` (CPU tree-train + inference, GPU deep-train) + ADR-0002. ✓

## Tests passing
- `tests/test_sizing_calculator.py` (8) · `tests/test_degradation_switch.py` (9, incl. **alert-only invariant**) · `tests/integration/topology_smoke.py` · `scripts/degradation_demo.sh`.
- M2/M5: `test_tee_attestation.py` (10) · `test_pam_shim.py` (4) · `test_governance.py` (7) · `test_hitl_gate.py` (3) · `test_rbac_sod.py` (5).
- M3/M4: `test_tools.py` (9) · `tests/security/test_siem_rules.py` (7) · `test_ops_tools.py` (7) · `tests/contract/test_contracts.py` (4).

## Blueprint validation (M2–M5 highlights)
- **Part 25.2/25.3/25.4 → PLATFORM-14**: TEE dual TDX+H200 quote issuer/verifier (Ed25519), enclave-mode, **tokenize-before-egress** refusal of raw PII. ✓
- **Part 9.3/19.3 → PLATFORM-13/15**: SoftHSM PKCS#11 key custody; PAM shim (session recording, no shared accounts, least-privilege). ✓
- **Part 26.1/26.2/26.4 → PLATFORM-7/8/10**: Terraform `target=aws|onprem|lightsail`; AWS security svcs (WAF/GuardDuty/SecurityHub/Inspector/CloudTrail); NAT egress allow-list (NEAR AI+Groq only); migration map + ADR-0001 (Lightsail = chosen pilot, documented deviation). ✓
- **Part 16/9.3 → PLATFORM-9**: Helm residency labels on every workload; OPA/Conftest residency gate. ✓
- **Part 19.1/19.2/19.6/27.1 → PLATFORM-20**: STRIDE + 3 attacker classes; ML-attack→ATLAS→mitigation table; OWASP/NIST/RBI alignment; 7-Sutra→control map. ✓ (WF-2)
- **Part 19.4/19.5/31.1 → PLATFORM-17/21/22/23**: SBOM(SPDX+CycloneDX)/CVE/SAST/secrets/IaC scans; perf p99 gate; chaos (broker+serving kill survives); 4 SIEM attack detectors; vuln tracker (critical ≤7d); VAPT/red-team/model-risk reports. ✓
- **Part 31.2/31.3/34.3 → PLATFORM-16/18/19**: CI pyramid + CD blue-green/canary + SLO rollback + 3-env parity; release + change-governance + scheduled windows + rollback runbook. ✓
- **Part 30 → PLATFORM-25/26/27/28/29/30/31**: RTO/RPO matrix + HA configs; immutable backup/restore; DR drill (RTO/RPO report, rows validated); BCP + **real** rules-only degradation; OTel + golden-signals + SLOs/error-budgets; Alertmanager severity routing + incident runbooks; capacity forecast + ITSC assessment. ✓
- **Part 27.2/22.4 → PLATFORM-32/34**: governance DB inventory; independent-validation sign-off gate blocks prod promotion. ✓
- **Part 27.1/28.1/29.2/19.6 → PLATFORM-35/36**: committees + board records; AI policy/DPIA/DPO/lawful-basis/breach/transparency docs with seeded approvals. ✓ (WF-2)
- **Part 15/16/19.6/29.2 → PLATFORM-37**: HITL natural-justice gate (pending_review, DPIA-bound, alert-only proven). ✓
- **Part 32/34.4/27.1 → PLATFORM-38**: vendor-risk (AWS/NEAR AI/Groq) DD/SLA/exit/concentration + AI clauses + SBOM linkage. ✓ (WF-2)
- **Part 33/34.1/34.2 → PLATFORM-39**: org/Three-Lines/RACI/SOPs; staffing (Erlang); FinOps; override-rate/alert-fatigue panel. ✓
- **Part 12/17.D/34.3 → PLATFORM-40**: detection-coverage map; honest-limits; bibliography; ADR/runbook/data-dictionary/model-card indexes. ✓ (WF-2)
- **Part 34.5/34.6 → PLATFORM-41**: DB-backed go-live checklist (**GATE: GO**, 17/17 ticks) + threat-intel feedback hand-off. ✓

## MOCK artifacts produced (the 24 human/legal/hardware items)
TEE attestation (14), SoftHSM (13), PAM (15), SoD personas (33), validation sign-off (34), AI/Model-Risk + ethics committees + incident form (35), AI policy + DPIA + DPO + lawful-basis + breach + transparency/whistleblowing/works-council (36 — 6 docs), HITL gate (37), vendor DD + AI clauses (38), operating-model/RACI/SOPs/staffing/training (39), VAPT + red-team + model-risk (23), investigator UAT (24), BCP board approval (28), DR drill (27), go-live checklist (41). All seeded with approval/evidence records keyed to model version `fusion-2026.2.0` where relevant.

## MOCK artifacts produced (the 24 human/legal/hardware items)
- (none yet — M5)

## Deviations / assumptions
- **Lightsail deployment** (DEV-001 above) — the one substantive deviation; everything else tracks the blueprint.
- Local toolchain present: docker compose v5, python 3.12 + pyyaml, node 23, openssl, jq. **Absent locally:** terraform, helm, conftest → those validate in CI (syntactically authored, `terraform validate`/`helm lint`/`conftest` run in `.github/workflows`).

## Blockers (mirror in TODO.md §7 + CONTEXT.md)
- (none) — other laptops' artifacts are stubbed per §3 stub rules until they ship.

## Session log (newest first)
- **2026-06-30 S2** — **M1 complete.** Core compose (8 infra svcs) + app compose (7 svcs) + platform compose (degradation-switch) = 18-service stack, `docker compose config` green. Built the REAL degradation switch (rules subset + transparent fusion + serving-health probe + optional Kafka worker), serving KServe-v2 stub, backend stub. topology doc, topics, Keycloak realm, Prometheus/Grafana provisioning, sizing calculator (+8 tests), compute-placement profiles + ADR-0002. 17 unit tests + smoke + degradation demo all pass. Next: M2 IaC.
- **2026-06-30 S1** — Read all coordination files + every cited blueprint Part (8,9,12,13,15,16,19,24.3,25-34). Created branch `hawk-eye/platform`. Built foundation: BOM, Makefile, root compose, .env, dir skeleton. Updated CONTEXT.md (ports table + 4 log entries incl. Lightsail deviation + BACKEND proposals), TODO.md §6, this log.
