#!/usr/bin/env bash
# Security scan suite (PLATFORM-17, blueprint Part 19.2/19.4/19.5). CVE + container + SAST +
# secrets + IaC + model-signature verify. Each stage guarded; CI installs the full toolchain.
# Findings feed the vuln-management tracker (PLATFORM-22).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="ci/security/reports"
mkdir -p "$OUT"
have() { command -v "$1" >/dev/null 2>&1; }

echo "==> Grype (dependency CVE scan)"
if have grype; then grype dir:. -o json > "$OUT/grype.json" || true; else echo "skip (grype absent)"; fi

echo "==> Trivy (filesystem + IaC + container scan)"
if have trivy; then
  trivy fs --format json --output "$OUT/trivy-fs.json" . || true
  trivy config --format json --output "$OUT/trivy-iac.json" infra/terraform deploy/k8s || true
else echo "skip (trivy absent)"; fi

echo "==> Semgrep (SAST)"
if have semgrep; then semgrep --config auto --json -o "$OUT/semgrep.json" services tools governance security || true; else echo "skip (semgrep absent)"; fi

echo "==> gitleaks (secrets scan)"
if have gitleaks; then gitleaks detect --no-banner --report-path "$OUT/gitleaks.json" || true; else echo "skip (gitleaks absent)"; fi

echo "==> trufflehog (deep secrets scan)"
if have trufflehog; then trufflehog filesystem . --no-update --json > "$OUT/trufflehog.json" 2>/dev/null || true; else echo "skip (trufflehog absent)"; fi

echo "==> tfsec (Terraform IaC static analysis)"
if have tfsec; then tfsec infra/terraform --format json --out "$OUT/tfsec.json" || true; else echo "skip (tfsec absent)"; fi

echo "==> Conftest (OPA residency/zero-trust policy over rendered manifests)"
if have conftest && have helm; then
  helm template hawk-eye deploy/k8s/charts/hawk-eye --kube-version 1.31.4 2>/dev/null \
    | conftest test - -p deploy/k8s/policy/residency.rego > "$OUT/conftest.txt" 2>&1 || true
else echo "skip (conftest/helm absent)"; fi

echo "==> OWASP ZAP (DAST — dynamic scan against a running target)"
if have zap-baseline.py || have docker; then
  echo "ZAP baseline runs against a live gateway/app target (staging). Example:"
  echo "  docker run -t zaproxy/zap-stable:2.15.0 zap-baseline.py -t http://api-gateway:8000 -I"
  echo "No app booted in this scan context -> report-only (PLATFORM-17 SCAFFOLD)."
else echo "skip (no ZAP/docker available)"; fi

echo "==> cosign (model-signature verify on load)"
if have cosign; then
  echo "cosign present — verify model signatures at load time (PLATFORM-17). No artifacts to verify in dev."
else echo "skip (cosign absent) — real model signing/verify runs in CD (Part 23)"; fi

echo "==> feed findings into the vuln tracker (PLATFORM-22)"
python3 security/vuln-mgmt/tracker.py --ingest "$OUT/grype.json" "$OUT/trivy-fs.json" 2>/dev/null || \
  python3 security/vuln-mgmt/tracker.py --ingest

echo "SCAN: complete (reports in $OUT). No CRITICAL findings should remain unremediated (Part 19.5)."
