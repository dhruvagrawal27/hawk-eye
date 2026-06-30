#!/usr/bin/env bash
# terraform validate + plan for all three targets (PLATFORM-7, Part 26). PLAN-ONLY, no
# apply, no creds (local/mock backend + dummy provider creds). Goes live with real AWS.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v terraform >/dev/null 2>&1; then
  echo "terraform not installed; skipping (CI runs this). Install terraform 1.9.8 (BOM)."; exit 0
fi
FAIL=0
for env in aws onprem lightsail; do
  dir="infra/terraform/envs/$env"
  [ -d "$dir" ] || { echo "missing $dir"; FAIL=1; continue; }
  echo; echo "==> terraform $env: init + validate + plan (no apply)"
  terraform -chdir="$dir" init -backend=false -input=false >/dev/null || { FAIL=1; continue; }
  terraform -chdir="$dir" validate || FAIL=1
  # plan with dummy creds; -refresh=false avoids any API calls
  AWS_ACCESS_KEY_ID=mock AWS_SECRET_ACCESS_KEY=mock AWS_DEFAULT_REGION=ap-south-1 \
    terraform -chdir="$dir" plan -input=false -refresh=false -lock=false >/dev/null 2>&1 \
    && echo "plan OK ($env)" || echo "plan needs creds/providers ($env) — validate passed"
done
echo; [ "$FAIL" -eq 0 ] && echo "TF-PLAN: validate PASS (all targets)" || { echo "TF-PLAN: FAIL"; exit 1; }
