#!/usr/bin/env bash
# Lint everything (PLATFORM-16, blueprint Part 31.1/31.2). Each step is guarded so the
# script runs locally even when a tool is absent (CI installs the full toolchain).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0
have() { command -v "$1" >/dev/null 2>&1; }
step() { echo; echo "==> $*"; }

step "python — ruff"
if have ruff; then ruff check tools services governance security tests || FAIL=1; else echo "skip (ruff absent)"; fi

step "python — black --check"
if have black; then black --check tools services governance security tests || FAIL=1; else echo "skip (black absent)"; fi

step "python — mypy (non-blocking, advisory)"
if have mypy; then mypy --ignore-missing-imports tools services 2>/dev/null || true; else echo "skip (mypy absent)"; fi

step "terraform fmt -check"
if have terraform; then terraform -chdir=infra/terraform fmt -check -recursive || FAIL=1; else echo "skip (terraform absent)"; fi

step "helm lint"
if have helm; then helm lint deploy/k8s/charts/hawk-eye || FAIL=1; else echo "skip (helm absent)"; fi

step "conftest (residency/zero-trust policy)"
if have conftest && have helm; then
  helm template deploy/k8s/charts/hawk-eye | conftest test --policy deploy/k8s/policy - || FAIL=1
else echo "skip (conftest/helm absent)"; fi

step "docker compose config"
if have docker; then
  python3 tools/bom_to_env.py >/dev/null 2>&1 || true
  docker compose -f docker-compose.yml config -q && echo "compose OK" || FAIL=1
else echo "skip (docker absent)"; fi

step "BOM drift check"
python3 tools/bom_to_env.py --check || FAIL=1

echo; [ "$FAIL" -eq 0 ] && echo "LINT: PASS" || { echo "LINT: FAIL"; exit 1; }
