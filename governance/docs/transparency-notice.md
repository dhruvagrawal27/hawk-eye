# Staff Transparency, Works-Council Engagement & Whistleblowing Notice — Hawk-Eye

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 29.2 (transparency to staff: employees should know monitoring
> exists, its purpose, and recourse — proportionality + works-council/union/legal engagement;
> explainability as a right; the "watch the watchers" principle), Part 28.1 (DPDP notice),
> Part 19.6 (privacy & proportionality; works-council review).
> **Regulators in scope:** DPDP Act 2023 + Rules 2025, RBI Fraud Risk Management MD 2024
> (whistleblowing / staff accountability), RBI ITGRCA MD 2023.
> **MOCK status:** the notice approval is a human act; the **record** is seeded in the
> governance DB (`policies` where `policy_type='transparency'`).

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| Policy name | Staff Transparency & Whistleblowing Notice |
| Policy type | `transparency` |
| Status | `board_approved` |
| Approved by | **HR + Works Council** |
| Approval date | **2026-02-28** |
| Resolution | **HR-2026-011** |
| Evidence record | `policies` (`resolution_id='HR-2026-011'`) → `governance/docs/out/transparency-notice.md` |

**Signatories:** Human Resources and the Works Council, recorded as resolution **HR-2026-011**
dated 2026-02-28, with DPO and Legal consultation.

---

## 1. Purpose of this notice

This notice tells you — our employees and privileged users — **that** behavioural fraud
monitoring exists, **why** it exists, **what** it does and does not do, **how** your rights are
protected, and **how** you can seek recourse. Transparency to staff is a FREE-AI **People First**
and **Fairness** expectation and a DPDP requirement, not merely good practice (Part 29.2).

---

## 2. What Hawk-Eye is — and what it is not

| Hawk-Eye **does** | Hawk-Eye **does not** |
|---|---|
| Analyse work-system telemetry (transactions, access, entitlements, privileged sessions) to surface **potential** fraud risk as an alert | **Auto-block** money, **auto-suspend** access, or **auto-classify** anyone as a fraudster — it is **ALERT-ONLY** |
| Attach **reason codes + a plain narrative** to every alert so it is explainable and contestable | Make any consequential decision about a person — **a human decides**, after a fair hearing |
| Compare behaviour to **peer-group-relative** norms | Use protected attributes (age, gender, caste, religion, region) as model inputs |
| Operate under independent fairness audits and a natural-justice gate | Operate as covert blanket surveillance — monitoring is proportionate and purpose-bound |

---

## 3. What is monitored, why, and on what lawful basis

- **Scope of monitoring:** work-system activity only — CBS transactions, payment messages,
  IAM/AD authentication, PAM privileged sessions, IGA entitlement changes, HR JML context, and
  DB-audit/DLP events — for the **single purpose** of detecting insider and privileged-user fraud.
- **Why:** the Bank has legal and regulatory duties (RBI Fraud Risk Management MD 2024, ITGRCA,
  KYC/AML) to detect and prevent fraud and to control privileged access.
- **Lawful basis:** mapped to DPDP's **closed legitimate-uses** list (fraud prevention / legal
  obligation / employment-function safeguarding) — **not** your consent, because the Bank does
  not rely on compelled consent. The full mapping is in `lawful-basis-map.md`.
- **Proportionality:** only data the detection needs is collected; PII is tokenized by default;
  investigators must hold a **separate, audited** permission to see your identity unmasked.

---

## 4. Your rights and recourse

- **Right to be informed** — this notice; you will be told if monitoring scope materially changes.
- **Explainability as a right** — if an alert leads to enquiry, you are entitled to the **reason
  codes and narrative** behind it; decisions are **contestable and defensible**.
- **Natural justice (HITL gate)** — **before** any classification, you receive a fair hearing; no
  adverse outcome is automated.
- **Data-principal rights (DPDP)** — access, correction, erasure (with lawful fraud/legal
  carve-outs), and **grievance**, with response SLAs, via the DPO.
- **Fairness protection** — the system is audited for disparate impact across grade, age, gender,
  region, department and tenure; protected attributes are never features; proxies are monitored.
- **Watch the watchers** — investigators' own actions are audited and subject to fairness review,
  so the system cannot be turned against any individual unchecked (Part 19.6 SoD).

---

## 5. Works-council / union engagement

The introduction and any material change to staff monitoring is conducted **with** the Works
Council / recognised unions, with Legal and the DPO:

- The Works Council was consulted on scope, proportionality, and recourse before sign-off
  (resolution **HR-2026-011**, 2026-02-28).
- Material changes to monitoring scope, model tier, or data categories are tabled with the
  Works Council before deployment.
- The Works Council may raise concerns through the grievance channel and to the AI Ethics
  Committee (which includes HR and Legal and is chaired by an independent member).

---

## 6. Whistleblowing notice

- **Protected disclosure:** you may report suspected fraud, misuse of the platform, or concerns
  about the monitoring itself through the Bank's **whistleblowing channel** without fear of
  retaliation; the channel is independent of the fraud-investigation line.
- **Non-retaliation:** good-faith disclosures are protected; retaliation is itself a disciplinary
  matter.
- **Confidentiality:** the identity of a whistleblower is protected to the extent permitted by
  law and investigation needs.
- **Escalation:** disclosures concerning the AI system's fairness or proportionality are routed
  to the AI Ethics Committee and the DPO.

---

## 7. Where to go

| Need | Channel |
|---|---|
| Exercise a data-principal right / raise a privacy grievance | Data Protection Officer (contact in `dpo-appointment.md`) |
| Contest an alert / decision | Natural-justice HITL process + your line manager / HR |
| Concern about fairness or proportionality | AI Ethics Committee (via HR / DPO) |
| Whistleblowing / protected disclosure | The Bank's independent whistleblowing channel |

---

## 8. Cross-references
- Lawful-basis map (closed DPDP list): `governance/docs/lawful-basis-map.md` (DPO-2026-003).
- DPIA (proportionality & risks): `governance/docs/dpia.md` (DPO-2026-004).
- DPO appointment & grievance contact: `governance/docs/dpo-appointment.md`.
- Breach notification: `governance/docs/breach-notification.md` (SEC-2026-021).
- AI Policy (People First / Fairness Sutras): `governance/docs/ai-policy.md` (BR-2026-014).
