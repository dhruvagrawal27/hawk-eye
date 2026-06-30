#!/usr/bin/env bash
# Generate SBOM in SPDX + CycloneDX (PLATFORM-17, blueprint Part 19.4 / Part 34.4 CERT-In v2.0).
# Syft over the repo. Guarded so it no-ops cleanly when syft is absent (CI installs it).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
OUT="ci/security/sbom"
mkdir -p "$OUT"
if ! command -v syft >/dev/null 2>&1; then
  echo "syft not installed; skipping SBOM (CI installs it). BOM: security_tools.syft 1.18.1"
  echo '{"note":"SBOM generated in CI (Syft SPDX+CycloneDX)"}' > "$OUT/sbom.placeholder.json"
  exit 0
fi
echo "==> Syft SBOM (SPDX json)"   && syft dir:. -o spdx-json="$OUT/sbom.spdx.json"
echo "==> Syft SBOM (CycloneDX)"   && syft dir:. -o cyclonedx-json="$OUT/sbom.cdx.json"
echo "SBOM written to $OUT (spdx + cyclonedx) — CERT-In v2.0 / RBI software-governance aligned."
