# Laptop 06 — PLATFORM — Working Log

> Your **own** file. Record decisions, files created, blueprint validations, deviations, and blockers. Update every session. Read `CONTEXT.md`, `BACKEND.md`, `TODO.md` first; append cross-cutting decisions to `CONTEXT.md`. You maintain the **service map / ports / env / secrets** section of `CONTEXT.md`. Full brief: [prompts/06_PLATFORM.md](../../prompts/06_PLATFORM.md).

## Status
- Branch: `hawk-eye/platform` · Owns: `platform/`, `infra/`, `.github/`, root `docker-compose.yml`, `tests/` harness, `deploy/`, `observability/`, `security/`, `governance/`, `ops/`, `ci/`, `tools/`, `services/`
- Milestone progress: **M1 DONE** ✓ · M2 next.

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
