# Data Protection Impact Assessment (DPIA) & Algorithmic Due Diligence — Hawk-Eye

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 28.1 (DPDP Act 2023 + Rules 2025; SDF obligations; DPIA for the
> employee-monitoring use case; algorithmic risk verification), Part 19.6 (privacy &
> proportionality; legal/HR/works-council review), Part 27 (MRM), Part 29 (fairness).
> **Regulators in scope:** DPDP Act 2023 + DPDP Rules 2025 (notified Nov 2025; ~18-month
> runway to full effect ~May 2027), RBI ITGRCA MD 2023, RBI Fraud Risk Management MD 2024.
> **MOCK status:** the DPO sign-off is a human act; the approval **record** is seeded in the
> governance DB (`dpia` table + `approvals` where `artifact_type='dpia_signoff'`).

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| DPIA name | Employee-Monitoring DPIA (combined with algorithmic due-diligence) |
| Scope | Staff behavioural fraud monitoring (insider & privileged-user) |
| Lawful basis | DPDP legitimate-uses (fraud prevention / legal obligation); proportionate |
| Risk rating | **High (mitigated)** |
| DPO | India-resident Data Protection Officer (appointed) |
| **DPO sign-off** | **DPO-2026-004**, dated **2026-03-01** (`approvals.artifact_type='dpia_signoff'`, approver role `dpo`) |
| Status | `approved` |
| Annual independent data-protection audit | Scheduled 2026-Q4 |
| Evidence record | `dpia` table + `approvals` (`resolution_id='DPO-2026-004'`) → `governance/docs/out/dpia.md` |

**Signatory:** India-resident Data Protection Officer, in consultation with Legal and HR
(Part 19.6). Recorded as approval **DPO-2026-004** dated 2026-03-01.

---

## 1. Why this DPIA exists

The Bank is a **Data Fiduciary** and, given the volume and sensitivity of the personal data
processed, will almost certainly be classified a **Significant Data Fiduciary (SDF)** under
the DPDP Act. SDF status triggers three obligations that converge on this document:

1. Appoint an **India-resident Data Protection Officer** (see `dpo-appointment.md`).
2. Conduct an **annual DPIA + independent data-protection audit**.
3. Perform **due diligence on algorithmic/technical systems** ("algorithmic risk
   verification") — Hawk-Eye's models are explicitly in scope for DPDP algorithmic
   due diligence.

This DPIA therefore serves a **dual purpose**: it is both the **employee-monitoring DPIA**
(mandated specifically by Part 28.1) and the **algorithmic-due-diligence assessment** of the
fraud-detection models. Penalties under DPDP reach **₹250 crore**, so this is treated as a
first-order control.

---

## 2. The processing being assessed

### 2.1 Nature, scope, context, purpose
- **Nature:** automated behavioural analysis of employee and privileged-user telemetry to
  surface potential insider fraud, producing **alerts with reason codes and a narrative** —
  **never** an automated adverse decision (ALERT-ONLY).
- **Scope:** transaction/posting logs (CBS), payment-message logs (SWIFT/RTGS/NEFT/UPI),
  IAM/AD auth logs, PAM privileged-session logs, IGA entitlement changes, HR joiner-mover-leaver
  feed, DB-audit / DLP events — mapped to the L0 unified event model.
- **Context:** a public-sector bank; the data subjects are primarily **employees** (and,
  incidentally, customers whose transactions an employee touches). This is a workplace-monitoring
  context with heightened power asymmetry and reputational sensitivity.
- **Purpose:** prevention, detection and investigation of insider/privileged-user fraud —
  a legal-obligation and fraud-prevention purpose, **purpose-bound** and not repurposed.

### 2.2 Personal data categories
| Category | Examples | Classification |
|---|---|---|
| Identity | employee_id, name, role/grade, department, branch | PII |
| Behavioural | login times, access patterns, transaction actions, entitlement changes | PII (behavioural) |
| Financial (incidental) | transaction amounts, beneficiary, PAN where present | Sensitive / PAN |
| Derived | risk scores, reason codes, peer-group features | Derived PII |

> **Build-time note:** the platform is built and demonstrated on **synthetic data only** — no
> real PII, credentials, or feeds. This DPIA assesses the **production** processing the design
> enables; the synthetic-only build is itself a privacy mitigation for the build phase.

---

## 3. Lawful basis & proportionality (DPDP-specific)

DPDP's **"legitimate uses" is a closed list, narrower than GDPR** — there is no open-ended
"legitimate interests" balancing clause. The fraud-monitoring purpose is mapped to DPDP's
permitted legitimate uses (fraud prevention / compliance with a legal obligation, including
RBI fraud-management and KYC/AML duties). The detailed per-activity mapping is in
`governance/docs/lawful-basis-map.md`; this DPIA records the **proportionality** test:

- **Necessity** — insider fraud is materially under-served by transaction-only controls;
  behavioural monitoring is necessary to detect it.
- **Data minimization** — only data the detection needs is collected; PII is tokenized before
  any LLM egress (Part 25.3); investigators see tokenized PII by default and must hold a
  separate, audited unmask permission.
- **Least intrusive means** — peer-group-relative scoring and reason-coded alerts, not blanket
  surveillance dossiers; ALERT-ONLY with a human decider.
- **Transparency** — staff are informed monitoring exists, its purpose, and their recourse
  (`transparency-notice.md`), with works-council/union/legal engagement.

---

## 4. Cross-border transfer assessment (the LLM angle)

Sending personal data outside India is subject to DPDP transfer restrictions. The design
mitigates this:

- **PII is hashed/tokenized before egress** (Part 25.3) — the external LLM sees behaviour +
  structure + tokens, never raw PII.
- The call runs to a **TEE** (Intel TDX + NVIDIA confidential compute); TLS terminates *inside*
  the enclave; **per-request attestation** is verified and stored. Even the provider cannot read
  the (already-tokenized) payload.
- **Documented destinations:** NEAR AI (`cloud-api.near.ai`, TEE-attested) primary; Groq
  (non-TEE, `tee_attested=false` logged, PII still tokenized) secondary; deterministic template
  fallback tertiary. Region of record is `ap-south-1`; residency intent is **in-India**.
- **Residency end-state:** the architecture prefers the **on-prem self-hosted `gpt-oss-120b`
  migration** (Part 26.4) — the bank's own H100/H200 in TDX — for full residency, with the same
  OpenAI-compatible interface and attestation guarantees.

The transfer is documented; the destination is confirmed not to be a restricted jurisdiction;
the residual transfer risk is **low**.

---

## 5. Risks and mitigations (employee-monitoring + algorithmic)

| # | Risk | Likelihood × Impact | Mitigation | Residual |
|---|---|---|---|---|
| R1 | Disproportionate surveillance of staff | M × H | Proportionality test (§3); ALERT-ONLY; minimization; transparency notice + works-council engagement | Low |
| R2 | Algorithmic bias / disparate flagging by grade/age/gender/region/dept/tenure | M × H | Fairness audit (Part 29.1); protected attributes never features; proxy monitoring; peer-group scoring; Ethics Committee review (`ETH-2026-006`) | Low |
| R3 | Feedback-loop bias amplification (EDD loop learns investigator bias) | M × M | Monitor label distributions; correct; continuous fairness monitoring (bias drifts) | Low–Med |
| R4 | Wrongful adverse outcome from an opaque decision | L × H | Explainability as a right (reason codes + narrative); **natural-justice HITL gate** before any classification; contestability | Low |
| R5 | Re-identification / PII exposure to investigators | M × H | Tokenization by default; separate audited unmask permission; field-level encryption; PAM | Low |
| R6 | Cross-border / provider exposure of personal data | L × H | Tokenize-before-egress + TEE attestation; on-prem migration path; documented transfer (§4) | Low |
| R7 | LLM hallucination misleading a human decider | M × M | Tier-4 grounding/hallucination validation; low temperature; narrative is explanatory only, never a score or action | Low |
| R8 | The system turned against the bank/an individual | L × H | SoD personas (builder/labeler/actor/administrator); "watch the watchers" audit (Part 19.6); immutable WORM log | Low |
| R9 | Excessive retention | M × M | Purpose-bound retention timelines; automated lifecycle deletion; erasure honoured with legal/fraud carve-outs | Low |
| R10 | Silent feed loss creating a blind spot | M × M | Ingestion reconciliation vs source-of-truth; data-quality SLAs (Part 32.2) | Low |

**Overall residual risk:** **High (mitigated)** — acceptable subject to the controls above and
continuous monitoring, as signed off by the DPO (DPO-2026-004).

---

## 6. Data-principal rights & retention

- **Rights** — access, correction, erasure and grievance, with response SLAs; erasure carries
  carve-outs for legal and fraud-investigation obligations.
- **Retention** — purpose-bound timelines; automated lifecycle deletion; tiered archival
  (hot → cold → archive) aligned to DPDP retention and RBI record-keeping.
- **Lineage** — end-to-end source → feature → model → alert lineage supports DPDP traceability
  and the natural-justice evidence base.

---

## 7. DPO conclusion

The DPO, having consulted Legal and HR (Part 19.6), concludes that the processing is **lawful,
proportionate and necessary**, that the residual risks are **mitigated to an acceptable level**,
and **approves** the processing subject to: (a) the controls in §5, (b) the lawful-basis mapping
in `lawful-basis-map.md`, (c) the transparency notice in `transparency-notice.md`, and (d) the
**annual independent data-protection audit** (scheduled 2026-Q4). Recorded as **DPO-2026-004**,
2026-03-01.

---

## 8. Cross-references
- DPO appointment + annual audit: `governance/docs/dpo-appointment.md`.
- Lawful-basis mapping (closed DPDP list): `governance/docs/lawful-basis-map.md`.
- Breach notification (PD-breach vs cyber): `governance/docs/breach-notification.md`.
- Staff transparency: `governance/docs/transparency-notice.md`.
- AI Policy (algorithmic governance): `governance/docs/ai-policy.md` (BR-2026-014).
