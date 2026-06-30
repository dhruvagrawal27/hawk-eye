# Data Dictionary — Index / Pointer

> **Owner:** PLATFORM (Laptop 06) maintains *this index* · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 5.1** (the unified event model). **Part 34.3** lists the
> data dictionary as a required, version-controlled, audit-accessible knowledge asset.
>
> **DATA owns the full dictionary.** This file is an **INDEX / stub** only. The authoritative
> field-by-field definitions for the **L0 unified event model** live with the **DATA** workstream
> (`data/`), and the canonical contract shape is published in **`BACKEND.md` §1**. Do not
> duplicate definitions here — point to the source of truth.

---

## Where the real dictionary lives

| Asset | Location | Owner |
|---|---|---|
| **L0 unified event JSON (canonical contract)** | [`BACKEND.md` §1](../BACKEND.md) | DATA defines the schema · BACKEND publishes the contract |
| **Full field-by-field dictionary** | `data/` (DATA workstream) | **DATA** |
| **Feature names / keys / synthetic dataset format** | `data/` | **DATA** |
| **Schema registry (runtime, versioned)** | Apicurio Schema Registry (:8085) | PLATFORM hosts · DATA defines schemas |

---

## The L0 event model — field groups (Part 5.1)

The unified event model is the foundation everything rests on. It is organised into **five field
groups** (blueprint Part 5.1; mirrored in `BACKEND.md` §1):

| Field group | What it captures | Examples (from `BACKEND.md` §1) |
|---|---|---|
| **Actor** | *Who* did it | `employee_id`, `role`, `dept`, `branch`, `tenure_days`, `peer_group`, `privileged_flag`, `leaver_flag` |
| **Action** | *What* was done | `verb` (e.g. `create_beneficiary`), `channel` (e.g. `cbs`), `maker_checker` (maker/checker) |
| **Object** | *What it was done to* | `beneficiary_id`, `account_id`, `amount`, `currency` |
| **Context** | *Circumstances* | `src_ip`, `device`, `geo`, `session_id`, `layer`, `is_off_hours` |
| **Linkage** | *Correlation keys* joining systems | SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account |

> **Linkage** is the join layer that makes cross-system typologies detectable (e.g. the SWIFT↔CBS
> reconciliation mismatch that catches the PNB/LoU mechanism — see
> [`detection-coverage-map.md`](./detection-coverage-map.md)).

### Canonical example (see `BACKEND.md` §1 for the live contract)

```json
{
  "event_id": "evt_8f2a1c90",
  "ts": "2026-06-30T02:14:07Z",
  "actor":  { "employee_id": "EMP-7f3a", "role": "ops_maker", "dept": "trade_finance", "...": "..." },
  "action": { "verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker" },
  "object": { "beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": null, "currency": "INR" },
  "context":{ "src_ip": "10.20.4.31", "device": "WS-114", "geo": "Mumbai", "session_id": "sess_55e1", "...": "..." }
}
```

---

## ID conventions (CONTEXT.md §6)

- `event_id` → `evt_*` · `alert_id` → `alr_*` · `entity_id` = `employee_id` (e.g. `EMP-7f3a`) ·
  `ring_id` → `RNG-*` · `audit_id` → `aud_*`.
- **Time:** UTC ISO-8601 (`...Z`); displayed in IST on the frontend.
- **Money:** integer minor units where possible; currency explicit (INR default).
- **PII:** tokenized before egress; re-identification (`POST /entities/{id}/unmask`) is a separate,
  audited permission (BACKEND.md §3, RBAC = Senior+).

---

## Privacy & proportionality note

Per [`honest-limits.md`](./honest-limits.md) and Part 15, the dictionary is governed by
**proportionality** — Hawk-Eye monitors **risk-relevant** signals, not everything. The field set
above is intentionally scoped; expanding it is a data-governance decision (DPDP Act 2023 /
Rules 2025; DPIA on employee monitoring — seeded sign-off **DPO-2026-004**).

---

*This is an index. The authoritative, exhaustive data dictionary is owned and maintained by the
**DATA** workstream in `data/`; the contract shape is in `BACKEND.md` §1; the runtime schemas live
in the Schema Registry (:8085).*
