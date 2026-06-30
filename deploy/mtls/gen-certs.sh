#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye — dev mTLS CA + per-service certificates with SPIFFE SAN URIs
# Owner: PLATFORM (Laptop 06)  ·  Task: PLATFORM-11  ·  Blueprint: Part 26.2 (mTLS),
#        Part 9.3, Part 19.3 (no shared/anonymous accounts — one identity per service)
# -----------------------------------------------------------------------------
# Creates a self-signed DEV certificate authority and one mTLS leaf certificate
# per platform service (CONTEXT.md §7), each carrying its SPIFFE identity in the
# SAN URI:  spiffe://hawk-eye/ns/default/sa/<service>
#
# This is the DEV stand-in for SPIRE-issued SVIDs (see ./README.md and ./spire/).
# In the real fabric, SPIRE issues short-lived, auto-rotated SVIDs with these same
# SPIFFE IDs; this script lets the local stack run mTLS without SPIRE.
#
# Properties:
#   * RUNNABLE  — pure openssl + bash, no external services.
#   * IDEMPOTENT — re-running does not regenerate existing valid material
#                  (use FORCE=1 to rebuild). The CA is created once and reused.
#   * NO SECRETS IN GIT — output goes to ./certs/ which is gitignored (keys never
#                  committed); a local .gitignore is written defensively.
#
# Usage:
#   ./gen-certs.sh            # generate CA (if absent) + any missing service certs
#   FORCE=1 ./gen-certs.sh    # rebuild everything from scratch
#   DAYS=825 ./gen-certs.sh   # override leaf validity (default 365)
# =============================================================================
set -euo pipefail

# --- Locate ourselves so the script is path-independent ----------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/certs"
CA_DIR="${CERT_DIR}/ca"

TRUST_DOMAIN="hawk-eye"
SPIFFE_NS="default"                       # k8s namespace in the SPIFFE path
CA_DAYS="${CA_DAYS:-3650}"                # dev CA: 10y
DAYS="${DAYS:-365}"                       # leaf certs: 1y (SPIRE uses minutes)
KEY_BITS="2048"
FORCE="${FORCE:-0}"

# --- Canonical service list (CONTEXT.md §7). ONE cert per service. ------------
# (compose service names; used both as CN/DNS SAN and as the SPIFFE sa/<service>)
SERVICES=(
  kafka
  schema-registry
  flink-jobmanager
  clickhouse
  redis
  postgres
  minio
  backend
  serving
  frontend
  keycloak
  mlflow
  airflow
  prometheus
  grafana
  alertmanager
  otel-collector
  vault
  tee-attestation
  pam-shim
  degradation-switch
  governance-api
  hitl-gate
)

# --- Preconditions -----------------------------------------------------------
command -v openssl >/dev/null 2>&1 || { echo "ERROR: openssl not found on PATH" >&2; exit 1; }

if [[ "${FORCE}" == "1" ]]; then
  echo "[mtls] FORCE=1 — removing ${CERT_DIR}"
  rm -rf "${CERT_DIR}"
fi

mkdir -p "${CA_DIR}"

# Defensive: keep generated key material out of git even if root .gitignore moves.
cat > "${CERT_DIR}/.gitignore" <<'EOF'
# Generated dev mTLS material — NEVER commit private keys.
*
!.gitignore
EOF

# --- Helper: SPIFFE ID for a service ----------------------------------------
spiffe_id() {
  local svc="$1"
  echo "spiffe://${TRUST_DOMAIN}/ns/${SPIFFE_NS}/sa/${svc}"
}

# =============================================================================
# 1. Dev Certificate Authority (created once, reused — idempotent)
# =============================================================================
CA_KEY="${CA_DIR}/ca.key"
CA_CRT="${CA_DIR}/ca.crt"

if [[ -f "${CA_KEY}" && -f "${CA_CRT}" ]]; then
  echo "[mtls] CA already present — reusing ${CA_CRT}"
else
  echo "[mtls] generating dev CA (${CA_DAYS}d) ..."
  openssl genrsa -out "${CA_KEY}" "${KEY_BITS}" 2>/dev/null
  chmod 600 "${CA_KEY}"
  openssl req -x509 -new -nodes -key "${CA_KEY}" -sha256 -days "${CA_DAYS}" \
    -subj "/O=Hawk-Eye/OU=platform/CN=Hawk-Eye Dev mTLS CA" \
    -out "${CA_CRT}" 2>/dev/null
  echo "[mtls]   -> ${CA_CRT}"
fi

# =============================================================================
# 2. Per-service leaf certificates with SPIFFE SAN URI (idempotent per service)
# =============================================================================
GEN_COUNT=0
SKIP_COUNT=0

for svc in "${SERVICES[@]}"; do
  svc_dir="${CERT_DIR}/${svc}"
  key="${svc_dir}/${svc}.key"
  csr="${svc_dir}/${svc}.csr"
  crt="${svc_dir}/${svc}.crt"
  bundle="${svc_dir}/${svc}.bundle.crt"   # leaf + CA, for servers that want a chain
  ext="${svc_dir}/${svc}.ext"
  sid="$(spiffe_id "${svc}")"

  if [[ -f "${key}" && -f "${crt}" && "${FORCE}" != "1" ]]; then
    SKIP_COUNT=$((SKIP_COUNT + 1))
    continue
  fi

  mkdir -p "${svc_dir}"

  # X.509v3 extensions: the SPIFFE ID is carried in subjectAltName URI.
  # Both serverAuth + clientAuth so the same cert works for mTLS in either role.
  cat > "${ext}" <<EOF
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names

[alt_names]
URI.1 = ${sid}
DNS.1 = ${svc}
DNS.2 = ${svc}.default.svc.cluster.local
DNS.3 = localhost
IP.1  = 127.0.0.1
EOF

  openssl genrsa -out "${key}" "${KEY_BITS}" 2>/dev/null
  chmod 600 "${key}"

  openssl req -new -key "${key}" \
    -subj "/O=Hawk-Eye/OU=service/CN=${svc}" \
    -out "${csr}" 2>/dev/null

  openssl x509 -req -in "${csr}" \
    -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
    -days "${DAYS}" -sha256 \
    -extfile "${ext}" \
    -out "${crt}" 2>/dev/null

  cat "${crt}" "${CA_CRT}" > "${bundle}"
  rm -f "${csr}" "${ext}"

  GEN_COUNT=$((GEN_COUNT + 1))
done

# =============================================================================
# 3. Summary
# =============================================================================
echo
echo "============================================================="
echo " Hawk-Eye dev mTLS material (PLATFORM-11)"
echo "-------------------------------------------------------------"
echo " trust domain : ${TRUST_DOMAIN}"
echo " CA cert      : ${CA_CRT}"
echo " output dir   : ${CERT_DIR}  (gitignored — keys NEVER committed)"
echo " services     : ${#SERVICES[@]}  (generated: ${GEN_COUNT}, reused: ${SKIP_COUNT})"
echo "-------------------------------------------------------------"
printf " %-22s %s\n" "SERVICE" "SPIFFE ID (SAN URI)"
for svc in "${SERVICES[@]}"; do
  printf " %-22s %s\n" "${svc}" "$(spiffe_id "${svc}")"
done
echo "-------------------------------------------------------------"
echo " Verify a cert's SPIFFE SAN, e.g.:"
echo "   openssl x509 -in ${CERT_DIR}/backend/backend.crt -noout -text | grep -A1 'Subject Alternative Name'"
echo " Each leaf is signed by the dev CA; verify with:"
echo "   openssl verify -CAfile ${CA_CRT} ${CERT_DIR}/backend/backend.crt"
echo "============================================================="
echo "[mtls] done. (Real fabric: SPIRE issues these SVIDs — see ./README.md, ./spire/)"
