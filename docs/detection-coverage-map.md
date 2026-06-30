# Detection Coverage Map — "does it solve each and everything?"

> **Owner:** PLATFORM (Laptop 06) · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 12** (Detection coverage map) — this file *reproduces*
> Part 12's table verbatim-in-spirit; the honest limits that accompany it live in
> [`honest-limits.md`](./honest-limits.md).
> **Golden rule reminder:** Hawk-Eye is **ALERT-ONLY** — every row below ends in a *human* EDD
> decision and (where warranted) a *human-raised* block request. The system **scores and
> explains; it never auto-blocks money** (Part 16; *SBI v. Rajesh Agarwal*, 2023).

This is the honest mapping of the reference document's fraud vectors to **how Hawk-Eye catches
them**, the **layer(s)** that fire, the **key signals/features**, and the **lane** each lands in.

---

## How to read this map

- **Layers (L0..L6 + L7).** `L1` = rules/BRE · `L2` = unsupervised/UEBA · `L3` = supervised GBDT
  (XGBoost/LightGBM + SHAP) · `L4` = sequence/time-series · `L5` = graph/relational ·
  `L6` = risk fusion (one calibrated 0–100 score) · `L7` = investigator dashboard.
- **Lane.**
  - **Fast** = real-time / near-real-time online path (event → feature → score → alert, seconds);
    the primary build.
  - **Slow** = batch / Early-Warning-Signal (EWS) path that surfaces over days–weeks–months
    (credit, entity, ghost-vendor, ghost-payroll, alert-suppression); feeds RBI **EWS/CRILC/FMR**.
  - **Fast/Slow** = has both a real-time tripwire and a slow-lane accumulation view.
- **Bold layers / lanes** mark the *primary* detector for that vector (matching the blueprint's
  emphasis).

---

## Coverage table (reproduces blueprint Part 12)

| Fraud vector (from the reference doc) | Caught by | Key features / signals | Lane |
|---|---|---|---|
| Reversal theft (branch) | L1 + L2 | reversal clustering per operator; deposit-then-reverse pattern | Fast |
| Dormant-account takeover | L1 + L2 | reactivation→activity; silent channel enrollment | Fast |
| Beneficiary-then-approve (toxic combo) | L1 + L3 + L5 | new-beneficiary→high-value latency; maker-checker pairing | Fast |
| SWIFT/LoU abuse (PNB mechanism) | **L1** | **SWIFT↔CBS reconciliation mismatch** (instrument with no CBS entry) | Fast |
| Suspense/nostro lapping | L1 + L2 | item aging; same person posts & reconciles | Fast/Slow |
| Rogue trading (mismarking, fictitious trades) | L1 + L2 + L4 | won't-take-leave; late/cancelled-rebooked trades; P&L-vs-mark divergence | Fast/Slow |
| Direct DB manipulation (privileged) | **L1 + L2** | **DB write with no app txn**; off-hours; out-of-scope access | Fast |
| Entitlement self-grant / temp admin | L1 | short-lived grants timed to transactions | Fast |
| Log tampering / control disablement | L1 | audit-config changes; logging gaps | Fast |
| Bulk data exfiltration | **L1 + L2 + L4** | download volume vs baseline; export to personal channel; leaver-window | Fast |
| Fake-vendor / billing | L1 + L3 + L5 | vendor=employee address; round/sequential invoices; single-client vendor | Fast/Slow |
| Alert suppression (AML watchers) | L2 + L3 | one analyst clearing disproportionate share; reopened-then-cleared | Slow |
| Ghost employees / payroll | L1 + L3 + L5 | no tax footprint; duplicated bank details | Slow |
| Collusion rings / embedded accomplices | **L5** | maker-checker subgraphs; referrer-cluster hiring; shared-identity links | Slow |
| Ghost/insider loans, inflated appraisal (credit) | **Slow lane** | thin docs; appraiser-is-borrower; disbursement-to-non-sanctioned-account | **Slow** |
| Executive financial-statement fraud / override | **Partial** | always-hits-target; close-control overrides; cultural KRIs | **Slow + non-technical controls** |

---

## Layer participation summary

| Layer | Vectors it is named in (above) |
|---|---|
| **L1 — Rules / BRE** | reversal theft · dormant takeover · beneficiary-then-approve · **SWIFT/LoU abuse (primary)** · suspense/nostro lapping · rogue trading · **direct DB manipulation** · entitlement self-grant · log tampering · **bulk exfiltration** · fake-vendor · ghost payroll |
| **L2 — Unsupervised / UEBA** | reversal theft · dormant takeover · suspense/nostro lapping · rogue trading · **direct DB manipulation** · **bulk exfiltration** · alert suppression |
| **L3 — Supervised GBDT** | beneficiary-then-approve · fake-vendor · alert suppression · ghost payroll |
| **L4 — Sequence / time-series** | rogue trading · **bulk exfiltration** |
| **L5 — Graph / relational** | beneficiary-then-approve · fake-vendor · ghost payroll · **collusion rings (primary)** |
| **Slow lane (EWS)** | suspense/nostro lapping · rogue trading · fake-vendor · alert suppression · ghost payroll · collusion rings · **credit/insider loans (primary)** · **executive override (partial)** |

---

## What this map *does not* claim

Three vectors are deliberately **not** sold as real-time wins — read them in
[`honest-limits.md`](./honest-limits.md):

1. **Credit/loan fraud is slow-lane only** — accelerated (years → weeks), not instant.
2. **Executive override / pure human collusion with no digital footprint** is only *partially*
   addressable by any system; it needs culture, whistleblowing, surprise audit, board oversight.
3. **A determined low-and-slow insider** can still drift a baseline; *mitigated, not eliminated*.

---

*Source of truth: blueprint Part 12. The fast lane (real-time insider/privileged behaviour) is the
primary build; the slow lane (credit/entity/EWS) is phased (Part 13). The system collapses
detection time and gives investigators a unified, explainable, prioritized view — it does not
promise the impossible.*
