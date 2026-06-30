# Business Continuity Plan (BCP) — Hawk-Eye (PLATFORM-28)

> Blueprint **Part 30.1** (board-approved BCP, ITGRCA) + **Part 18** (rules-only fallback).
> **MOCK:** board approval is a human/legal act; the approval RECORD is seeded in the
> governance DB (`policies` type=`bcp`, resolution `BRC-2026-008`). The **graceful-degradation
> switch is REAL** (`services/degradation-switch`, PLATFORM-4) — it demonstrably keeps the
> pipeline alerting on L1-rules-only when ML serving is down.

## Approval (seeded record)
- **Approved by:** Board Risk Committee · **Date:** 2026-03-04 · **Resolution:** BRC-2026-008
- **Review cadence:** annual + after any major incident (ITGRCA).

## 1. Business Impact Analysis (BIA)
| Function | Impact if down | Max tolerable outage | Priority |
|---|---|---|---|
| Alert scoring + delivery | Fraud goes undetected in real time | minutes | Critical |
| Investigator dashboard | Triage stalls; SLA/TAT breach risk | < 1 hour | Critical |
| Audit/WORM logging | Loss of regulator/natural-justice trail | ≈ 0 (never) | Critical |
| Model retraining/registry | Detection quality decays slowly | days | Medium |
| Governance reporting | Board/RBI reporting delayed | days | Medium |

## 2. RTO / RPO
See `ops/dr/rto-rpo-matrix.md` (audit-log RPO ≈ 0; alerting RTO minutes; no SPOF).

## 3. Continuity / fallback procedures (graceful degradation)
- **ML serving down →** the **degradation switch** routes scoring to **L1-rules-only**
  (BACKEND's BRE); every event is marked for **re-scoring** (`hawkeye.rescore`) when ML
  recovers — **nothing is dropped**. This is the Part 18 continuity feature *and* the BCP
  degradation mode. Proven by `make degradation-demo`.
- **Kafka broker loss →** RF3 + multi-rack; consumers fail over; no data loss.
- **DB primary loss →** restore from immutable backup + promote replica (`make dr-drill`).
- **Total site loss →** failover to DR site (multi-DC/AZ); runbook `ops/dr/runbooks/`.
- **LLM gateway down →** NEAR AI → Groq → **deterministic template** (UI never breaks, Part 25.4).

## 4. ALERT-ONLY under degradation
In **every** continuity mode the system still only **alerts** — it never auto-blocks money
(golden rule #1). The HITL gate (PLATFORM-37) continues to hold classifications for human
review. Degradation reduces sophistication (rules-only), never the human-decides guarantee.

## 5. Testing
- BCP test: annual tabletop + `make dr-drill` (restore drill with RTO/RPO timings).
- Chaos: `make chaos` injects broker + serving-node failure; the pipeline survives via
  degradation (Part 30.1 cyber-resilience drill).
