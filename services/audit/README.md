# `services/audit/` — WORM audit writer + verifier (DATABASE-6)

> **Owner:** DATABASE. Drains the append-only `hawkeye.audit` topic (DATABASE-5)
> and seals each record **immutably** to the MinIO `audit-archive` object-lock
> bucket, with per-record **hash-chaining** + a **daily Merkle anchor**. A
> verification CLI re-walks the chain + roots and reports PASS/FAIL. Watch the
> watchers — investigators' own actions are audited (Part 19.3). Blueprint Part 8
> (l.311), Part 9.3 (l.364), Part 19.2 (l.626), Part 19.3 (l.634).

## Files
| File | Purpose |
|---|---|
| `audit_schema.py` | Canonical audit envelope + action/target enums + `canonical_bytes`/`compute_record_hash` (single source; mirrors `audit_event.avsc`). |
| `hashchain.py` | Per-record chain (`record_hash = H(content ‖ prev_hash)`) + domain-separated daily Merkle root + `verify_chain`. |
| `worm_store.py` | Object-lock store (`MinioWormStore`) + filesystem WORM emulation (`LocalWormStore`) behind one interface. |
| `worm_writer.py` | Single-writer sink: validate → chain → seal; `finalize_day` writes the Merkle anchor; `run_kafka` is the live loop. |
| `verify_cli.py` | Re-walk chain + recompute roots → PASS/FAIL with the first divergent record. |

## How tamper-evidence works
1. **Chain:** each sealed record carries `prev_hash` (prior record's hash) and
   `record_hash = SHA-256(canonical_content ‖ 0x00 ‖ prev_hash)`. Altering any
   record breaks every later link; `verify_chain` returns the first break.
2. **Merkle anchor:** the day's record hashes fold into a binary Merkle tree; the
   **daily root** is the value a regulator pins. Re-deriving it from the sealed
   records must reproduce the pinned root.
3. **Immutability:** records land in the object-lock `audit-archive` bucket
   (COMPLIANCE retention) — a delete/overwrite within retention is **server-rejected**.
   The verifier proves *detection*; object-lock proves *prevention*.

## Run
```bash
# live: consume the audit topic and seal to WORM
KAFKA_BOOTSTRAP=localhost:29092 MINIO_ENDPOINT=localhost:9001 python -m services.audit.worm_writer
# seal the daily Merkle anchor for a date
python -m services.audit.worm_writer --finalize-day 2026-06-30
# verify (PASS on an untouched chain; FAIL with the offending record on tamper)
python -m services.audit.verify_cli
```

## Record classes covered (acceptance)
alerts · dispositions · model versions · feature snapshots · rule/threshold
changes · investigators' own actions (who-viewed-whom) · registry access · PII
unmask · narrative audit memos — the `AuditAction` enum in `audit_schema.py`.

## AWS swap
`audit-archive` → S3 Object Lock (COMPLIANCE) + SSE-KMS; the writer/verifier are
unchanged (only the client config differs). The daily Merkle roots can additionally
be anchored to an external notary / WORM appliance for defence-in-depth.
