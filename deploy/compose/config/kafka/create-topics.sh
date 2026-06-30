#!/usr/bin/env bash
# Declares the Hawk-Eye topic topology (PLATFORM-2/4, blueprint Part 9.1).
# Mirrors infra/kafka/topics.yaml. Idempotent (--if-not-exists). Runs once via kafka-init.
set -euo pipefail
BS="kafka:9092"
KT="/opt/kafka/bin/kafka-topics.sh"

echo "[kafka-init] waiting for broker ${BS} ..."
for i in $(seq 1 30); do
  if "$KT" --bootstrap-server "$BS" --list >/dev/null 2>&1; then break; fi
  sleep 2
done

create() {  # name partitions retention_ms [cleanup.policy]
  local name="$1" parts="$2" ret="$3" policy="${4:-delete}"
  echo "[kafka-init] topic ${name} (p=${parts}, retention.ms=${ret}, policy=${policy})"
  "$KT" --bootstrap-server "$BS" --create --if-not-exists \
    --topic "$name" --partitions "$parts" --replication-factor 1 \
    --config "retention.ms=${ret}" --config "cleanup.policy=${policy}"
}

create hawkeye.events.l0       6 604800000   delete
create hawkeye.events.enriched 6 604800000   delete
create hawkeye.scores          6 604800000   delete
create hawkeye.alerts          3 2592000000  delete
create hawkeye.audit           3 -1          compact
create hawkeye.feedback        3 7776000000  delete
create hawkeye.rescore         6 604800000   delete
create hawkeye.dlq             3 1209600000  delete

# --- DATA-side topic aliases (topic-name convergence, CONTEXT.md log) --------
# DATA's data/config.py publishes to events.raw / events.signals / alerts / audit.
# Until DATA adopts the hawkeye.* namespace, PLATFORM also provisions DATA's names so
# both producers/consumers work. (events.raw == hawkeye.events.l0; events.signals ==
# enriched/recon signals.) Partitioned by employee_id like their hawkeye.* counterparts.
create events.raw              6 604800000   delete
create events.signals          6 604800000   delete
create alerts                  3 2592000000  delete
create audit                   3 -1          compact

echo "[kafka-init] topics ready:"
"$KT" --bootstrap-server "$BS" --list
