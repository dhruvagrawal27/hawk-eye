# SOP — Beneficiary Fraud Investigation (PLATFORM-39)

> Blueprint **Part 33.3** (per-typology SOP) + **Part 1/6** (the toxic-combination signal:
> *new beneficiary created then high-value payment approved by the same maker-checker pair*).
> **ALERT-ONLY:** this playbook ends in a human decision and, where warranted, a request-block
> through the HITL natural-justice gate — it never auto-blocks money.

## 1. Trigger (what fired)
A Hawk-Eye alert on the **new-beneficiary → high-value-payment latency** toxic-combination:
a beneficiary/standing-instruction created, then a high-value payment to it within a short
window, often by the **same maker and checker** (maker-checker collusion candidate). May be
reinforced by L3 (gradient boosting + SHAP), L5 (graph), and a hard L1 rule.

## 2. EDD steps (Enhanced Due Diligence)
1. **Read the explanation panel** — which rule fired (SoD/typology provenance), SHAP top
   features, and any graph evidence (maker↔checker linkage). Note the risk score and layer
   contributions.
2. **Reconstruct the timeline** (actor→action→object): beneficiary `create_beneficiary` →
   `approve_payment`; check the **latency** and whether maker = checker or an always-the-same
   pair (Part 6.2 maker-checker pairing frequency).
3. **Validate the beneficiary** — is it a real, expected counterparty? New, never-before-seen,
   or recently modified? Cross-check against the customer/vendor master.
4. **Profile the actor** — role, department, tenure, `privileged_flag`, peer deviation
   (acting outside one's role), recent entitlement changes, `leaver_flag`/notice period.
5. **Check segregation of duties** — did one identity effectively control both maker and
   checker roles (toxic combination in practice)?
6. **Corroborate** — is there a legitimate business justification (documented approval,
   genuine invoice/LC)? Contact the business line via the **Consulted** path (RACI) without
   tipping off the subject.

## 3. Evidence collection
- Pull from the **immutable WORM audit log**: the `create_beneficiary` and `approve_payment`
  events, maker/checker identities, timestamps, channel, amount/currency, instrument.
- Snapshot the explanation (rule provenance + SHAP + graph) for the case file — this is the
  **SAR/FMR-filing-defensible** record.
- Record chain-of-custody (who pulled, when). Do **not** mutate source records.

## 4. Disposition (human decides)
- **True fraud** → request-block via HITL gate (CRO/MLRO accountable, RACI 2.2); open case.
- **False positive** → close-as-FP with reason (legit counterparty/justification).
- **Inconclusive** → hold for more signal / senior review.
- Every disposition is captured as a **label** (feedback loop). Disposition within TAT.

## 5. Escalation
High-value + high-risk (e.g., large amount + same-pair maker-checker + leaver) →
**Senior Investigator + Vigilance Officer immediately**; SLA timer starts.

## 6. Handoff — HR disciplinary + law-enforcement referral
On confirmed insider fraud:
- **HR disciplinary:** package the evidence file (timeline + explanation + audit-log extract)
  to HR for internal disciplinary action; respect **natural justice / due process** (the
  employee is heard before adverse action).
- **Law-enforcement referral:** refer to **CBI / ED** as warranted (and file RBI FMR/CFR per
  Fraud MD 2024); the **Vigilance Officer co-signs** the external referral; Legal is Consulted.
- Feed any novel variant into `km-wiki.md` → new rule + synthetic-library scenario.
