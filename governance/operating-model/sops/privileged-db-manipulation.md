# SOP — Privileged DB Manipulation Investigation (PLATFORM-39)

> Blueprint **Part 33.3** (per-typology SOP) + **Part 6.3** (the privileged "god-mode" tier:
> *DB write with no corresponding app transaction*, entitlement self-grant, short-lived
> privilege grants timed around transactions). This is the **seam** the system is built for —
> the privileged admin acting below the application layer (PNB-style). **ALERT-ONLY:** ends in
> a human decision; never auto-blocks.

## 1. Trigger (what fired)
A Hawk-Eye alert on **DB-write-without-app-txn** — a direct database mutation
(`modify_account`, `reverse_txn`, direct `UPDATE`) with **no correlated application
transaction**, or an **entitlement self-grant** / short-lived privilege grant timed around a
transaction. Sourced from DB-audit + PAM-session telemetry correlated to the app-txn stream
(L1 hard rule + L4 anomaly + L5 graph for entitlement chains).

## 2. EDD steps
1. **Read the explanation** — which rule fired (DB-write-without-app-txn / self-grant); the
   correlation key that failed to join app-txn ↔ DB-write (Part 5 linkage).
2. **Reconstruct the privileged session** (actor→action→object) from PAM logs: login →
   privilege grant → DB write → (grant revoked?). Note timing of the grant relative to the
   write (short-lived privilege timed around a transaction is a strong signal).
3. **Confirm the missing app leg** — is there genuinely **no** application transaction backing
   the DB write? Reconcile against CBS/app logs. A true god-mode write bypasses maker-checker.
4. **Check entitlements** — did the actor **self-grant** the right, or hold a toxic combination
   (conflicting entitlements; acted on a self-granted right, Part 6.3)? Use of shared/service/
   orphaned accounts or dormant privileged-account activation?
5. **Assess impact** — which accounts/balances/instruments were altered; was a transaction
   reversed, a balance changed, an account modified?
6. **Corroborate** — any approved break-glass/emergency-change ticket? Validate against the
   change-management/CAB record; absence of a ticket strengthens the case.

## 3. Evidence collection
- Pull **PAM privileged-session logs** (CyberArk/BeyondTrust), **DB-audit** records, the
  app-txn stream, and entitlement-change logs from the **immutable WORM audit log**.
- Capture the failed app-txn↔DB-write correlation and the entitlement timeline as the case
  file (defensible for SAR/FMR and internal forensics).
- Record chain-of-custody; preserve PAM session recordings; do not mutate audit records.

## 4. Disposition (human decides)
- **True fraud/manipulation** → request-block / revoke entitlement via HITL gate; isolate the
  account with Security/PAM owners; open case.
- **False positive** → close-as-FP (approved break-glass change with valid ticket).
- **Inconclusive** → hold; tighten PAM monitoring on the actor.
- Capture as a label; disposition within TAT.

## 5. Escalation
Any confirmed god-mode write to live financial data → **Vigilance + CISO + Security Incident
Response (RACI 2.5) immediately**; PAM owners revoke standing rights; ISC informed.

## 6. Handoff — HR disciplinary + law-enforcement referral
- **HR disciplinary:** evidence package (PAM session + DB-audit + entitlement timeline) to HR;
  natural justice / due process before adverse action; suspend privileged access pending review.
- **Law-enforcement referral:** **CBI / ED** as warranted; file RBI FMR/CFR (Fraud MD 2024);
  Vigilance co-signs; Legal Consulted; CISO confirms no broader compromise (incident response).
- Feed novel privilege-abuse tradecraft into `km-wiki.md` → rule + synthetic-library scenario.
