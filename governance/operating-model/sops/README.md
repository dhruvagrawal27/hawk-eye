# Investigation SOPs / Playbooks — Hawk-Eye (PLATFORM-39)

> Blueprint **Part 33.3** (investigation playbooks/SOPs per typology) + **Part 6/7**
> (typology features). These are the **1st-line (Fraud/Vigilance) operating procedures** for
> running **Enhanced Due Diligence (EDD)** on a Hawk-Eye alert. Every SOP follows the same
> spine: **Trigger → EDD steps → Evidence collection → Disposition → Handoff (HR disciplinary
> + CBI/ED referral)**. The system is **ALERT-ONLY**: the SOP ends in a human decision; it
> never auto-blocks money (golden rule #1). A request-block routes through the **HITL
> natural-justice gate** before any classification.

## Playbook index

| Typology | SOP | Blueprint signal |
|---|---|---|
| Beneficiary fraud | `beneficiary-fraud.md` | new-beneficiary → high-value-payment latency (toxic-combination) |
| Data exfiltration | `exfiltration.md` | off-hours bulk download / export before resignation (leaver_flag) |
| Privileged DB manipulation | `privileged-db-manipulation.md` | DB-write-without-app-txn (god-mode tier) |
| Collusion ring | `collusion-ring.md` | always-the-same maker-checker pair; mule/relational graph |
| Dormant-account takeover | `dormant-takeover.md` | dormant-reactivation → drain |

Plus `km-wiki.md` — the living knowledge-management wiki that captures **new** typologies
back into the rules engine + synthetic red-team library (closing the loop).

## Common conventions (apply to every SOP)

- **Canonical event model:** every signal is an **actor → action → object** event (Part 5.x).
- **SoD:** the investigator runs the SOP as the `actor` persona; they may not build models,
  label outside the EDD loop, or administer the platform.
- **Evidence integrity:** all evidence is pulled from the **immutable WORM audit log**;
  nothing is mutated; chain-of-custody is recorded (who pulled what, when).
- **Natural justice:** before any adverse classification, the employee gets due process via
  the HITL gate (Part 29.2 / RBI).
- **TAT:** disposition within RBI examination TAT (≤30 days); high-severity escalates
  immediately (Part 33.3 escalation matrix).
- **Referral chain:** confirmed insider fraud → **HR disciplinary** (internal) **and**
  **law-enforcement referral to CBI / ED** (external), per the enforcement chain in the
  original doc. Vigilance Officer co-signs external referrals.
- **Disposition is a label:** every outcome (fraud / FP / inconclusive) is written back to the
  feedback loop and, if novel, to `km-wiki.md`.
