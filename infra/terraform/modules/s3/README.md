# Module: `s3` (PLATFORM-7) — SCAFFOLD

Two S3 buckets, both **SSE-KMS encrypted**, **versioned**, **object-lock enabled**,
**public access fully blocked**.

| Bucket | Purpose | Object-lock mode | Retention |
|---|---|---|---|
| `<prefix>-artifacts` | models + synthetic datasets | `GOVERNANCE` | 365 d |
| `<prefix>-audit` | CloudTrail WORM audit log | `COMPLIANCE` (immutable) | ~7 y |

- **Blueprint:** Part 26.1 (S3 SSE-KMS / versioned / object-lock). The COMPLIANCE
  lock on the audit bucket gives a tamper-proof audit trail (Part 19) and aligns to
  RBI record-keeping.
- **Migration (Part 26.4):** `S3 → MinIO` (on-prem, same S3 API; object-lock + WORM
  supported). See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied. DATABASE owns bucket *contents*; PLATFORM
  owns the bucket infra.
