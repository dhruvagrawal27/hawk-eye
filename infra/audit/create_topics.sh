#!/usr/bin/env bash
# =============================================================================
# Hawk-Eye — create the append-only AUDIT topics (DATABASE-5)
# Blueprint: Part 8 (l.311), Part 19.3 (l.634).
# -----------------------------------------------------------------------------
# Idempotent. Creates `hawkeye.audit` (+ `.dlq`) with append-only semantics:
#   cleanup.policy=delete, retention.ms=-1 (infinite), compaction OFF.
#
# Works against either a real Kafka broker (DATA/PLATFORM cluster) OR the local
# single-broker Redpanda fallback shipped in infra/storage/docker-compose.storage.yml
# (so DATABASE never blocks on DATA's cluster — golden-rule "stub, never block").
#
# Usage:
#   KAFKA_BOOTSTRAP=localhost:29092 AUDIT_TOPIC_RF=1 AUDIT_MIN_ISR=1 \
#     ./infra/audit/create_topics.sh
# Override KAFKA_CLI to point at a container, e.g.:
#   KAFKA_CLI="docker exec hawkeye-redpanda rpk" ./infra/audit/create_topics.sh
# =============================================================================
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP:-localhost:29092}"
RF="${AUDIT_TOPIC_RF:-3}"
MIN_ISR="${AUDIT_MIN_ISR:-2}"
PARTITIONS="${AUDIT_PARTITIONS:-3}"

log() { printf '[create_topics] %s\n' "$*"; }

# ---- Detect an available admin CLI ------------------------------------------
# Prefer an explicit Apache-Kafka binary path, then rpk (Redpanda), then
# kafka-topics.sh on PATH, then a known container. Allow full override (KAFKA_CLI).
if [[ -n "${KAFKA_TOPICS_BIN:-}" ]]; then
  MODE="kafka"; KT="${KAFKA_TOPICS_BIN}"
elif [[ -n "${KAFKA_CLI:-}" ]]; then
  MODE="custom"
elif command -v rpk >/dev/null 2>&1; then
  MODE="rpk"
elif command -v kafka-topics.sh >/dev/null 2>&1; then
  MODE="kafka"
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^hawkeye-redpanda$'; then
  MODE="rpk-docker"
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^hawkeye-kafka$'; then
  MODE="kafka-docker"
else
  log "ERROR: no Kafka/Redpanda admin CLI found (rpk / kafka-topics.sh / container)."
  log "Bring up infra/storage/docker-compose.storage.yml (redpanda) or point KAFKA_CLI at the DATA cluster."
  exit 2
fi
log "using mode=${MODE} bootstrap=${BOOTSTRAP} rf=${RF} min_isr=${MIN_ISR} partitions=${PARTITIONS}"

# ---- Per-mode primitives -----------------------------------------------------
rpk_create() { # name partitions extra_configs...
  local name="$1" parts="$2"; shift 2
  local args=(topic create "$name" -p "$parts" -r "$RF" --brokers "$BOOTSTRAP")
  for c in "$@"; do args+=(-c "$c"); done
  ${RPK} "${args[@]}" 2>&1 | grep -v 'TOPIC_ALREADY_EXISTS' || true
  # Ensure configs even if the topic already existed.
  for c in "$@"; do ${RPK} topic alter-config "$name" --set "$c" --brokers "$BOOTSTRAP" >/dev/null 2>&1 || true; done
}

kafka_create() { # name partitions extra_configs...
  local name="$1" parts="$2"; shift 2
  local cfg=()
  for c in "$@"; do cfg+=(--config "$c"); done
  ${KT} --bootstrap-server "$BOOTSTRAP" --create --if-not-exists \
    --topic "$name" --partitions "$parts" --replication-factor "$RF" "${cfg[@]}" || true
  # Reconcile configs on an existing topic.
  for c in "$@"; do
    ${KT/kafka-topics/kafka-configs} --bootstrap-server "$BOOTSTRAP" --alter \
      --entity-type topics --entity-name "$name" --add-config "$c" >/dev/null 2>&1 || true
  done
}

case "$MODE" in
  rpk)         RPK="rpk" ; CREATE=rpk_create ;;
  rpk-docker)  RPK="docker exec hawkeye-redpanda rpk" ; CREATE=rpk_create ;;
  kafka)       KT="${KT:-kafka-topics.sh}" ; CREATE=kafka_create ;;
  kafka-docker)KT="docker exec hawkeye-kafka /opt/kafka/bin/kafka-topics.sh" ; CREATE=kafka_create ;;
  custom)      RPK="${KAFKA_CLI}" ; CREATE=rpk_create ;;  # assume rpk-compatible
esac

# ---- Create the append-only audit topics ------------------------------------
APPEND_ONLY_CFG=(
  "cleanup.policy=delete"
  "retention.ms=-1"
  "retention.bytes=-1"
  "min.insync.replicas=${MIN_ISR}"
  "unclean.leader.election.enable=false"
)

log "creating hawkeye.audit (append-only, infinite retention, compaction off) ..."
$CREATE "hawkeye.audit" "$PARTITIONS" "${APPEND_ONLY_CFG[@]}"

log "creating hawkeye.audit.dlq ..."
$CREATE "hawkeye.audit.dlq" "1" "${APPEND_ONLY_CFG[@]}"

log "done. Verify with: rpk topic describe hawkeye.audit  (or kafka-topics.sh --describe)"
