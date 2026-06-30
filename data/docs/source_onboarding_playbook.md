# Source-Onboarding Playbook (DATA-17)

> Blueprint Part 32.3 (l.1308–1309). A repeatable, auditable procedure for bringing a new
> source system into the L0 pipeline. Placed under `data/docs/` (not the shared `docs/`) to
> avoid colliding with another laptop. Onboarding status per source is tracked in code by
> `data/ingest/onboarding_status.py` and surfaced to the program dashboard.

## The 8 stages (run in order; each gates the next)

| # | Stage | What happens | Exit criterion |
|---|---|---|---|
| 1 | **Discovery** | Catalogue the source (system, owner, fields, volume, sensitivity, feed mechanism — CDC vs batch). | Source profile recorded in the data catalog (DATA-26). |
| 2 | **Schema mapping** | Map every source field to the L0 model (`data/schemas/l0_event.py`); identify Linkage keys (SWIFT↔CBS, app-txn↔DB-write, maker↔checker). | A connector `to_l0()` mapping reviewed against the data dictionary. |
| 3 | **Connector build** | Implement the adapter on `connectors/base_adapter.py` (CDC→Kafka fast lane or periodic batch). Mock fixtures first (SCAFFOLD), live feed later. | Adapter yields events that pass `validate_event`. |
| 4 | **DQ rules** | Add Great-Expectations/Pandera-style checks (`governance/quality/expectations.py`): completeness, validity, freshness, schema conformance, range/null, distribution. | DQ suite green on a sample; a corrupted fixture is caught. |
| 5 | **Backfill** | Load historical data to ClickHouse + object store (partitioned Parquet by date/source). | Backfill counts reconcile vs source-of-truth (`ingest/count_recon.py`). |
| 6 | **Lineage validation** | Register source→feature→model→alert lineage (`lineage/lineage.py`) with dataset hash + feature-set version. | Lineage record present and hash-stable. |
| 7 | **Shadow** | Run the source through the pipeline in shadow mode (scores, no alerts) to measure baseline volume. | Shadow run completes; baseline alert volume measured. |
| 8 | **Promote** | Flip the source live (or keep SCAFFOLD until creds exist). Schema-registry compatibility = BACKWARD so the source can evolve safely. | Sign-off recorded; status = `promoted`. |

## Reliability requirements (every source — DATA-17, Part 32.2)
- **Idempotent dedupe** by deterministic `event_id` (`make_id`); **dead-letter queue** for poison messages; **retries with backoff**; **backpressure** hooks. (Circuit-breaker/bulkhead patterns are owned by BACKEND/PLATFORM.)
- **Count reconciliation** of ingested-vs-source counts on a schedule to detect *silent feed loss* — a missing feed is a blind spot a fraudster could exploit.

## Status tracking
`data/ingest/onboarding_status.py` keeps each source's current stage and exposes
`dashboard()` → a list of `{source, stage, lane, status}` for the program dashboard.
Stages advance only when the exit criterion passes.

## Source inventory (initial)
CBS (Finacle/Flexcube/BaNCS/T24), Payments (SWIFT/RTGS/NEFT/IMPS/UPI + GL/suspense/nostro + treasury),
IAM/AD, PAM (CyberArk/BeyondTrust), VPN, DB-audit, DLP/egress, HR/HRMS (joiner-mover-leaver), IGA/entitlement.
All currently **SCAFFOLD** (mock fixtures → L0); promote to live when feeds + creds exist.
