# DR Failover Runbook (PLATFORM-27, blueprint Part 30.1)

> Documented, **rehearsed** failover to the DR site. Evidence of rehearsal:
> `make dr-drill` (`scripts/dr-drill.sh`) — backup → teardown → restore → **validate row
> counts** → failover toggle → RTO/RPO report. RTO/RPO targets: `ops/dr/rto-rpo-matrix.md`.

## Roles
- **Incident Commander (IC)** — declares DR, owns the timeline, comms.
- **SRE on-call** — executes the failover steps.
- **DBA** — restore + row-count validation.
- **Comms** — stakeholder + (if cyber) RBI/CERT-In liaison (Part 28.1, 6h).

## Pre-conditions
- Latest immutable backup present (`ops/backup/backup.sh`, object-lock/WORM).
- Standby site replicating (Kafka RF3 cross-rack, ClickHouse replicated, Postgres replica).

## Failover steps
1. **Declare** DR (IC). Start the RTO clock. Page on-call (Alertmanager severity=critical).
2. **Freeze** writes to the failing primary (if reachable) to bound RPO.
3. **Restore / promote:**
   - Postgres/governance: `ops/backup/restore.sh` → validate row counts (must match).
   - ClickHouse: promote replicas; verify shard/replica health.
   - Kafka: consumers fail over to surviving brokers (RF3) — usually no manual action.
   - Serving: scoring continues via the **degradation switch (rules-only)** during the gap
     (Part 18/30.1) — the pipeline never fully stops (alert-only preserved).
4. **Repoint** the app + dashboard to the DR endpoints (DNS / service mesh).
5. **Validate:** `make topology-smoke`; SLO dashboards (`observability/`) green; audit-log
   intact (RPO≈0); `make go-live` evidence unaffected.
6. **Toggle** failover state to standby-active; stop the RTO clock; record measured RTO/RPO.
7. **Communicate** restoration; if a cyber incident, file RBI/CERT-In per
   `ops/incident-mgmt/runbooks/incident-response.md`.

## Failback
Reverse once the primary is healthy: re-sync from DR → primary, validate, switch back in a
scheduled window (Part 31.3), post-mortem (`postmortem-template.md`).

## Evidence
Each drill emits `ops/dr/out/drill-report-<ts>.json` with measured RTO/RPO + row-count match —
the artifact the go-live checklist (PLATFORM-41) and Internal Audit consume.
