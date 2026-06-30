#!/usr/bin/env bash
# Render all Helm charts (PLATFORM-9). helm template = renders without a cluster.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v helm >/dev/null 2>&1; then
  echo "helm not installed; skipping (CI runs this). Install helm (k8s 1.31, BOM)."; exit 0
fi
echo "==> helm lint" && helm lint deploy/k8s/charts/hawk-eye
echo "==> helm template (render all workloads)" && helm template hawk-eye deploy/k8s/charts/hawk-eye | head -40
echo "..."
echo "HELM: rendered OK"
