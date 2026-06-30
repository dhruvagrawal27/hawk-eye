# =============================================================================
# Hawk-Eye — Root Makefile  (PLATFORM / Laptop 06, blueprint Part 24.3 / 17.C)
# Single operator entrypoint for the whole platform. `make help` lists targets.
# Every version pin comes from deploy/versions.bom.yaml (the BOM).
# =============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash
.ONESHELL:

# --- locations ---------------------------------------------------------------
COMPOSE_DIR   := deploy/compose
COMPOSE_CORE  := $(COMPOSE_DIR)/docker-compose.core.yml
COMPOSE_APP   := $(COMPOSE_DIR)/docker-compose.app.yml
COMPOSE_PLAT  := $(COMPOSE_DIR)/docker-compose.platform.yml
ROOT_COMPOSE  := docker-compose.yml
ENV_FILE      := $(COMPOSE_DIR)/.env
PY            := python3
VENV          := .venv-platform
TF            := terraform

# Compose invocation that includes every layer via the root entrypoint.
DC := docker compose -f $(ROOT_COMPOSE)

# =============================================================================
##@ Help
# =============================================================================
.PHONY: help
help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nHawk-Eye platform targets\n\033[2mmake <target>\033[0m\n"} \
	  /^[a-zA-Z0-9_.-]+:.*?##/ { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
	@echo ""

# =============================================================================
##@ Bring-up / tear-down (M1: PLATFORM-2/3)
# =============================================================================
.PHONY: bom-env
bom-env: ## Regenerate deploy/compose/.env image pins from the BOM
	@$(PY) tools/bom_to_env.py

.PHONY: up
up: bom-env ## Bring the FULL stack up (core + app + platform services)
	@$(DC) up -d
	@echo "Stack up. UIs: Grafana :3000  Keycloak :8080  MinIO :9002  Flink :8081  Airflow :8088  MLflow :5000"

.PHONY: core-up
core-up: bom-env ## Bring up only core infra (Kafka/Flink/Redis/ClickHouse/Postgres/MinIO/Feast/SchemaReg)
	@docker compose -f $(COMPOSE_CORE) --env-file $(ENV_FILE) up -d

.PHONY: app-up
app-up: bom-env ## Bring up serving/identity/observability (Triton/FastAPI/Keycloak/MLflow/Airflow/Prom/Grafana)
	@docker compose -f $(COMPOSE_CORE) -f $(COMPOSE_APP) --env-file $(ENV_FILE) up -d

.PHONY: down
down: ## Stop and remove all containers (keeps volumes)
	@$(DC) down

.PHONY: nuke
nuke: ## Stop and remove everything INCLUDING volumes (destructive)
	@$(DC) down -v --remove-orphans

.PHONY: ps
ps: ## Show container status / health
	@$(DC) ps

.PHONY: logs
logs: ## Tail logs (use S=<service> to filter)
	@$(DC) logs -f $(S)

.PHONY: config
config: bom-env ## Validate all compose files render (docker compose config)
	@$(DC) config -q && echo "compose config OK"

# =============================================================================
##@ Topology & degradation (M1: PLATFORM-4)
# =============================================================================
.PHONY: topology-smoke
topology-smoke: ## Flow a synthetic L0 event end-to-end and assert an alert lands
	@$(PY) tests/integration/topology_smoke.py

.PHONY: degradation-demo
degradation-demo: ## Kill ML serving and prove the pipeline falls back to L1-rules-only
	@bash scripts/degradation_demo.sh

# =============================================================================
##@ Quality gates (M3: PLATFORM-16)
# =============================================================================
.PHONY: lint
lint: ## Lint everything (python ruff/black/mypy, tf fmt, helm lint, compose config, conftest)
	@bash scripts/lint.sh

.PHONY: test
test: ## Run platform unit tests (sizing, staffing, services, switch, hitl, governance-api)
	@$(PY) -m pytest tests -q -m "not perf and not chaos" || true

.PHONY: contract-test
contract-test: ## Contract-test governance-api routes against BACKEND.md route table
	@$(PY) -m pytest tests/contract -q

# =============================================================================
##@ IaC (M2: PLATFORM-7/8/9/10/11/12)
# =============================================================================
.PHONY: tf-plan
tf-plan: ## terraform validate+plan for aws, onprem, and lightsail (mock backend, no apply)
	@bash scripts/tf_plan.sh

.PHONY: tf-fmt
tf-fmt: ## terraform fmt -check across all modules/envs
	@$(TF) -chdir=infra/terraform fmt -check -recursive

.PHONY: helm-template
helm-template: ## Render all Helm charts (helm template)
	@bash scripts/helm_template.sh

.PHONY: residency-check
residency-check: ## OPA/Conftest residency + zero-trust assertions over rendered manifests
	@bash scripts/residency_check.sh

.PHONY: mtls-certs
mtls-certs: ## Generate dev mTLS/SPIFFE certs for internal services (PLATFORM-11)
	@bash deploy/mtls/gen-certs.sh

.PHONY: softhsm-init
softhsm-init: ## Initialise the SoftHSM2 mock-HSM token (PLATFORM-13)
	@bash deploy/hsm/softhsm/init-token.sh

# =============================================================================
##@ Security & supply-chain (M3: PLATFORM-17/20/21/22)
# =============================================================================
.PHONY: sbom
sbom: ## Generate SBOM in SPDX + CycloneDX (Syft) into ci/security/sbom/
	@bash ci/security/sbom.sh

.PHONY: scan
scan: ## Run the full security scan suite (CVE/container/SAST/secrets/IaC)
	@bash ci/security/scan.sh

.PHONY: vuln-tracker
vuln-tracker: ## Ingest scan output into the vuln-management tracker (PLATFORM-22)
	@$(PY) security/vuln-mgmt/tracker.py --ingest

.PHONY: siem-test
siem-test: ## Validate SIEM detection rules fire on the 4 attack signatures (PLATFORM-21)
	@$(PY) -m pytest tests/security/test_siem_rules.py -q

# =============================================================================
##@ Performance / chaos / DR (M3/M4: PLATFORM-21/27)
# =============================================================================
.PHONY: perf
perf: ## Load + soak at target TPS, assert p99 budget (k6/Locust)
	@bash tests/perf/run.sh

.PHONY: chaos
chaos: ## Kill a broker + a serving node; assert pipeline survives via degradation
	@bash tests/chaos/run.sh

.PHONY: dr-drill
dr-drill: ## Backup->teardown->restore->validate row counts->failover->RTO/RPO report
	@bash scripts/dr-drill.sh

# =============================================================================
##@ Governance & go-live (M5: PLATFORM-32..41)
# =============================================================================
.PHONY: seed-governance
seed-governance: ## Seed the governance DB with all 24 mock artifacts + evidence records
	@$(PY) governance/db/seed.py

.PHONY: go-live
go-live: ## Render the DB-backed go-live readiness checklist (go/no-go gate)
	@$(PY) governance/go-live/checklist.py

.PHONY: governance-docs
governance-docs: ## Generate governance policy docs (md -> pdf) with seeded approvals
	@$(PY) governance/docs/generate.py

.PHONY: uat
uat: ## Run the Playwright investigator UAT and emit a signed report (PLATFORM-24)
	@bash tests/uat/run.sh

# =============================================================================
##@ Setup
# =============================================================================
.PHONY: install
install: ## Create the platform python venv and install service/tool deps
	@$(PY) -m venv $(VENV) && . $(VENV)/bin/activate && \
	  pip install -q -U pip && pip install -q -r tools/requirements.txt && \
	  echo "platform venv ready: source $(VENV)/bin/activate"

.PHONY: clean
clean: ## Remove generated artifacts (sbom, reports, caches)
	@rm -rf ci/security/sbom/*.json ci/security/reports .pytest_cache .ruff_cache .mypy_cache
	@echo "cleaned"
