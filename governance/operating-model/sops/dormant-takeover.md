# SOP — Dormant-Account Takeover Investigation (PLATFORM-39)

> Blueprint **Part 33.3** (per-typology SOP) + **Part 6** (the branch-banking red flag:
> *dormant-account reactivation → activity → drain*). A classic insider pattern — a dormant
> account is reactivated and quietly drained, often by staff who control the reactivation.
> **ALERT-ONLY:** ends in a human decision; never auto-blocks.

## 1. Trigger (what fired)
A Hawk-Eye alert on **dormant-reactivation → drain**: an account flagged dormant is
reactivated (status change / re-KYC / contact-detail change) and then shows
activity/outflows — frequently with a recently modified beneficiary or standing instruction.
L1 hard rule (dormant-reactivation) + L4 sequence anomaly; may chain into beneficiary-fraud or
collusion signals.

## 2. EDD steps
1. **Read the explanation** — which rule fired; the dormancy duration, who reactivated, and the
   gap between reactivation and first outflow.
2. **Reconstruct the sequence** (actor→action→object): dormant status → reactivation event
   (who, role, channel) → contact/beneficiary modification → outflow. A short reactivation→drain
   latency is a strong signal.
3. **Profile the reactivating actor** — is reactivation within their role? Peer deviation?
   Did the **same actor** reactivate **and** initiate/approve the outflow (SoD breach)?
4. **Validate the customer** — is the genuine account holder aware/contactable through
   independently-verified (not newly-changed) contact details? Were contact details altered
   just before reactivation (account-takeover hallmark)?
5. **Check linkages** — new/modified beneficiary, standing instruction, or
   employee↔customer-account link (Part 6 linkage) suggesting insider control.
6. **Corroborate** — legitimate reactivation (genuine customer return, re-KYC) vs engineered
   takeover; consult the branch via the RACI Consulted path without alerting the subject.

## 3. Evidence collection
- Pull the dormancy flag, reactivation event, contact-detail/beneficiary modification, and
  outflow events from the **immutable WORM audit log**; capture the reactivating actor's session.
- Snapshot the sequence evidence and the reactivation→drain timeline for the case file.
- Record chain-of-custody; preserve the pre-modification contact details (proof of takeover).

## 4. Disposition (human decides)
- **True takeover/fraud** → request-block of outflows + re-freeze the account via HITL gate;
  open case; protect the genuine customer.
- **False positive** → close-as-FP (genuine customer reactivation with independent verification).
- **Inconclusive** → hold; verify customer identity through independent channels.
- Capture as a label; disposition within TAT.

## 5. Escalation
Active drain or same-actor reactivate-and-approve (SoD breach) → **Senior Investigator +
Vigilance immediately**; notify the branch and protect the customer's funds (alert, human
decides to hold).

## 6. Handoff — HR disciplinary + law-enforcement referral
- **HR disciplinary:** evidence package (reactivation timeline + altered contact details +
  outflow) to HR; natural justice / due process before adverse action.
- **Law-enforcement referral:** **CBI / ED** as warranted; file RBI FMR/CFR (Fraud MD 2024);
  Vigilance co-signs; Legal Consulted; coordinate customer remediation.
- Feed novel takeover tradecraft into `km-wiki.md` → rule + synthetic-library scenario
  (e.g., contact-detail-change-before-reactivation as a new hard red flag).
