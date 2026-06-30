#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye — MinIO object-store bootstrap (DATABASE-1)
# Blueprint: Part 23.3 (encrypted-at-rest, versioned+object-lock, least-privilege,
#            l.864-865); Part 21.5 (object store + partitioned Parquet, l.823-824);
#            Part 9.3 (immutability/WORM, field-level encryption, l.363-364).
# -----------------------------------------------------------------------------
# Idempotent. Creates the 4 app buckets + 2 ClickHouse tiering buckets, turns ON
# versioning (all 4 app buckets) + object-lock (models + audit-archive, set at
# CREATE time), enables SSE-S3 auto-encryption at rest, sets default WORM
# retention, and installs 5 least-privilege policies + service users.
#
# Runs in the `minio/mc` container (compose `minio-setup`) or with a local `mc`.
# Env (defaults match deploy/compose/.env):
#   MINIO_ENDPOINT=http://minio:9001  MINIO_ROOT_USER=hawkeye  MINIO_ROOT_PASSWORD=hawkeye_dev_pw
#   POLICY_DIR=/policies (mounted)     AUDIT_LOCK_DAYS=3650     MODELS_LOCK_DAYS=30
# =============================================================================
set -euo pipefail

ALIAS="hawkeye"
ENDPOINT="${MINIO_ENDPOINT:-http://minio:9001}"
ROOT_USER="${MINIO_ROOT_USER:-hawkeye}"
ROOT_PW="${MINIO_ROOT_PASSWORD:-hawkeye_dev_pw}"
POLICY_DIR="${POLICY_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/policies" && pwd)}"
AUDIT_LOCK_DAYS="${AUDIT_LOCK_DAYS:-3650}"    # 10y WORM hold for audit (DPDP/RBI)
MODELS_LOCK_DAYS="${MODELS_LOCK_DAYS:-30}"    # governance hold for model artifacts

MC="${MC:-mc}"
log() { printf '[minio-bootstrap] %s\n' "$*"; }

# ---- wait for MinIO + set alias ---------------------------------------------
log "connecting to ${ENDPOINT} ..."
for i in $(seq 1 30); do
  if ${MC} alias set "${ALIAS}" "${ENDPOINT}" "${ROOT_USER}" "${ROOT_PW}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  [[ "$i" == "30" ]] && { log "ERROR: MinIO not reachable"; exit 2; }
done

# ---- buckets: object-lock MUST be set at creation ---------------------------
# models + audit-archive → created WITH object-lock (immutable artifacts + WORM).
log "creating object-lock buckets (models, audit-archive) ..."
${MC} mb --with-lock --ignore-existing "${ALIAS}/models"
${MC} mb --with-lock --ignore-existing "${ALIAS}/audit-archive"
log "creating standard buckets (datasets, feature-snapshots) ..."
${MC} mb --ignore-existing "${ALIAS}/datasets"
${MC} mb --ignore-existing "${ALIAS}/feature-snapshots"
log "creating ClickHouse tiering buckets (clickhouse-cold, clickhouse-archive) ..."
${MC} mb --ignore-existing "${ALIAS}/clickhouse-cold"
${MC} mb --ignore-existing "${ALIAS}/clickhouse-archive"

# ---- versioning ON (all 4 app buckets) --------------------------------------
log "enabling versioning ..."
for b in models datasets feature-snapshots audit-archive; do
  ${MC} version enable "${ALIAS}/${b}"
done

# ---- default object-lock (WORM) retention (COMPLIANCE = no early delete) -----
log "setting default WORM retention ..."
${MC} retention set --default COMPLIANCE "${AUDIT_LOCK_DAYS}d" "${ALIAS}/audit-archive"
${MC} retention set --default COMPLIANCE "${MODELS_LOCK_DAYS}d" "${ALIAS}/models"

# ---- SSE-S3 encryption at rest ----------------------------------------------
# Requires MinIO started with a local KMS key (MINIO_KMS_SECRET_KEY=hawkeye-key:<b64>,
# set in the compose). 1:1 swap to SSE-KMS: point MINIO_KMS_KES_* at Vault/KES and
# run `mc encrypt set sse-kms hawkeye-key <bucket>` instead.
log "enabling SSE-S3 auto-encryption at rest ..."
for b in models datasets feature-snapshots audit-archive clickhouse-cold clickhouse-archive; do
  ${MC} encrypt set sse-s3 "${ALIAS}/${b}" 2>/dev/null \
    || log "WARN: SSE-S3 not enabled on ${b} (is MINIO_KMS_SECRET_KEY set?) — continuing"
done

# ---- least-privilege policies + service users -------------------------------
log "installing least-privilege policies from ${POLICY_DIR} ..."
declare -A USERS=(
  [models-writer]="svc-ml-packager"
  [models-reader]="svc-serving-loader"
  [datasets-rw]="svc-data-pipeline"
  [audit-writer]="svc-worm-writer"
  [read-only-auditor]="svc-auditor"
)
for policy in models-writer models-reader datasets-rw audit-writer read-only-auditor; do
  ${MC} admin policy create "${ALIAS}" "${policy}" "${POLICY_DIR}/${policy}.json" 2>/dev/null \
    || ${MC} admin policy add "${ALIAS}" "${policy}" "${POLICY_DIR}/${policy}.json" 2>/dev/null || true
  user="${USERS[$policy]}"
  # Dev-only service password (synthetic). In prod these come from Vault (PLATFORM).
  ${MC} admin user add "${ALIAS}" "${user}" "${user}-dev-pw" 2>/dev/null || true
  ${MC} admin policy attach "${ALIAS}" "${policy}" --user "${user}" 2>/dev/null \
    || ${MC} admin policy set "${ALIAS}" "${policy}" "user=${user}" 2>/dev/null || true
done

# ---- dataset partition-layout marker (Part 21.5) ----------------------------
# datasets/{dataset_name}/dt=YYYY-MM-DD/source={src}/part-*.parquet (by date/source).
# DVC remote points here; each curated set carries a content-hash sidecar.
log "writing dataset partition-layout README into datasets bucket ..."
TMP="$(mktemp)"; cat > "${TMP}" <<'EOF'
Hawk-Eye dataset layout (DATABASE-1, blueprint Part 21.5):
  datasets/{dataset_name}/dt=YYYY-MM-DD/source={src}/part-*.parquet
Curated training sets carry a sidecar:
  datasets/{dataset_name}/{version}/_content_hash.json   (sha256 + feature_set_version)
DVC remote = s3://datasets (endpoint = this MinIO). Versioning is ON.
EOF
${MC} cp "${TMP}" "${ALIAS}/datasets/_LAYOUT.txt" >/dev/null 2>&1 || true
rm -f "${TMP}"

log "verifying ..."
${MC} ls "${ALIAS}/" || true
log "object-lock status (models, audit-archive):"
${MC} retention info "${ALIAS}/audit-archive" 2>/dev/null || true

log "done. Buckets: models* datasets feature-snapshots audit-archive* (*=object-lock+versioned)"
