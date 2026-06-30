# Lawful-Basis Map — Fraud Monitoring of Staff under the DPDP Act (Closed Legitimate-Uses List)

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 28.1 (DPDP's "legitimate uses" is a **closed list, narrower than
> GDPR**; fraud monitoring of staff must be mapped to a valid basis and documented; engage
> legal + HR early — Part 19.6).
> **Regulators in scope:** DPDP Act 2023 + DPDP Rules 2025; RBI Fraud Risk Management MD 2024;
> RBI KYC/AML duties; RBI ITGRCA MD 2023.
> **MOCK status:** the lawful-basis policy approval is a human/legal act; the **record** is
> seeded in the governance DB (`policies` where `policy_type='lawful_basis'`).

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| Policy name | DPDP Lawful-Basis Mapping (employee monitoring) |
| Policy type | `lawful_basis` |
| Status | `board_approved` |
| Approved by | **DPO + Legal** |
| Approval date | **2026-02-25** |
| Resolution | **DPO-2026-003** |
| Linked DPIA | DPO-2026-004 (employee-monitoring DPIA) |
| Evidence record | `policies` (`resolution_id='DPO-2026-003'`) → `governance/docs/out/lawful-basis-map.md` |

**Signatories:** Data Protection Officer and Legal, recorded as resolution **DPO-2026-003**
dated 2026-02-25.

---

## 1. Why this map is necessary

Unlike the GDPR, the **DPDP Act does not contain an open-ended "legitimate interests" balancing
basis.** Personal data may be processed only for purposes within a **closed enumerated list** of
**"legitimate uses"** (plus consent). Workplace fraud monitoring is **not** a consent-based
activity in any meaningful sense — staff cannot freely refuse, so consent is the wrong basis and
must not be relied upon. Each processing activity must therefore be deliberately mapped to a
**specific legitimate use** and **documented**, engaging Legal and HR early (Part 19.6).

This document provides that **per-activity** mapping. It is the lawful-basis evidence the DPIA
(`dpia.md`) relies on and the audit (`dpo-appointment.md`) tests against.

---

## 2. The DPDP legitimate uses relied upon (and why)

| Legitimate use relied upon | Why it fits fraud monitoring of staff |
|---|---|
| **Compliance with a legal obligation / function under law** | RBI's Fraud Risk Management MD 2024, KYC/AML obligations, and ITGRCA require the Bank to detect and report fraud and to maintain controls over privileged access — a legal/regulatory obligation the Bank must discharge. |
| **Prevention/detection of fraud and protection against loss** | Insider and privileged-user fraud detection is the core, purpose-bound objective; the processing is necessary and proportionate to it (DPIA §3). |
| **Performance of employment-related functions / safeguarding the employer from loss or liability** | Workplace monitoring narrowly scoped to fraud risk falls within employment-context legitimate uses, subject to proportionality and transparency. |

> **Explicitly not relied upon:** open-ended "legitimate interests" (does not exist under DPDP)
> and **employee consent** (not freely given in an employment power-asymmetry; not a valid basis
> for compelled monitoring).

---

## 3. Per-processing-activity lawful-basis map

| # | Processing activity | Source feed | Personal data | DPDP legitimate use | Proportionality control |
|---|---|---|---|---|---|
| P1 | Ingest & normalise transaction/posting events to L0 | CBS (Finacle/Flexcube/BaNCS/T24) | employee_id, txn metadata, amounts | Legal obligation (RBI fraud/AML); fraud prevention | Minimization; tokenization; need-bound fields |
| P2 | Payment-message monitoring & SWIFT↔CBS reconciliation | SWIFT/RTGS/NEFT/UPI logs | actor id, message metadata | Legal obligation; fraud prevention | Reconciliation only; no content beyond fraud signal |
| P3 | Authentication-pattern monitoring | IAM / Active Directory (via SIEM) | login times, source, success/fail | Fraud prevention; employment-function safeguarding | Behavioural features only; no surveillance dossier |
| P4 | Privileged-session monitoring | PAM (CyberArk/BeyondTrust) | privileged-session logs | Legal obligation (ITGRCA privileged-access control) | PAM-scoped; "watch the watchers" audited |
| P5 | Entitlement-change monitoring (self-grant, toxic combos) | IGA / entitlement systems | entitlement-change events | Legal obligation; fraud prevention | SoD/toxic-combination logic; minimal fields |
| P6 | Joiner-Mover-Leaver context enrichment | HR / HRMS | role/grade, dept, branch, JML status | Employment function; fraud prevention | Context signal only; **protected attributes never used as model features** |
| P7 | Data-layer / DLP activity monitoring | DB audit / DLP | data-access events | Legal obligation; fraud prevention | Minimization; exfiltration-pattern focus |
| P8 | Risk scoring & alerting (L2–L6) | derived | risk scores, reason codes | Fraud prevention; legal obligation | **ALERT-ONLY**; explainability; HITL natural-justice gate |
| P9 | Narrative generation (LLM) | derived (tokenized) | tokenized features only | Fraud prevention | PII tokenized before egress; TEE attestation; no raw PII leaves perimeter |
| P10 | EDD disposition & feedback labelling | investigator input | labels, dispositions | Legal obligation; fraud prevention | SoD personas; label-distribution fairness monitoring |
| P11 | Immutable audit logging | derived | actor actions, decisions | Legal obligation; accountability | WORM/immutable; near-zero RPO; "watch the watchers" |
| P12 | Re-identification (unmask) on demand | re-id vault | token↔real mapping | Fraud investigation (legal obligation) | Separate, **audited** unmask permission; senior+ only |

---

## 4. Cross-cutting safeguards (apply to all activities)

- **Purpose limitation** — data is used only for insider/privileged-user fraud detection; no
  repurposing for performance management, HR discipline beyond the referral chain, or marketing.
- **Data minimization** — only fields the detection needs; protected attributes (age, gender,
  caste, religion, region) are **never** model features, and proxies (e.g., branch) are monitored.
- **Retention** — purpose-bound timelines; automated lifecycle deletion; erasure honoured with
  lawful fraud/legal carve-outs.
- **Transparency** — staff informed of monitoring, purpose and recourse (`transparency-notice.md`).
- **Human decision** — ALERT-ONLY; natural-justice HITL gate precedes any classification.

---

## 5. Cross-references
- Employee-monitoring DPIA (proportionality & risks): `governance/docs/dpia.md` (DPO-2026-004).
- DPO appointment & annual audit: `governance/docs/dpo-appointment.md`.
- Staff transparency & whistleblowing: `governance/docs/transparency-notice.md` (HR-2026-011).
- Breach notification: `governance/docs/breach-notification.md` (SEC-2026-021).
- AI Policy: `governance/docs/ai-policy.md` (BR-2026-014).
