# Data Protection Officer (DPO) Appointment Record & Annual Independent Audit Summary — Hawk-Eye

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 28.1 (DPDP SDF obligations — appoint an **India-resident DPO**;
> conduct an **annual DPIA + independent data-protection audit**), Part 19.6 (governance &
> privacy).
> **Regulators in scope:** DPDP Act 2023 + DPDP Rules 2025.
> **MOCK status:** the appointment is a human/legal act; the appointment and audit **records**
> are seeded in the governance DB (`dpia` table — `dpo` field; annual-audit field).

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| Role | Data Protection Officer (DPO) |
| Residency | **India-resident** (DPDP SDF requirement) |
| Status | Appointed |
| Reporting line | Board of Directors (independent of the lines of business it oversees) |
| Linked DPIA sign-off | **DPO-2026-004**, 2026-03-01 (employee-monitoring DPIA) |
| Annual independent data-protection audit | **Scheduled 2026-Q4** |
| Evidence record | `dpia` table (`dpo='India-resident DPO (appointed)'`, `audit_report` field) |

**Basis of appointment:** As a (presumptive) **Significant Data Fiduciary**, the Bank is
obliged under the DPDP Act 2023 to appoint an **India-resident DPO** who is responsible to the
Board, and to commission an **annual DPIA and independent data-protection audit**. This record
evidences that obligation for the Hawk-Eye platform.

---

## 1. Appointment particulars

| Particular | Detail |
|---|---|
| Designation | Data Protection Officer, accountable to the Board |
| Residency / jurisdiction | India-resident (mandatory for an SDF) |
| Independence | Independent of the fraud, model-development and investigation functions it oversees (no SoD conflict — Part 19.6) |
| Contactability | Published grievance/contact channel for data principals (staff and customers) |
| Term & review | Standing appointment; reviewed annually with the DPIA cycle |

### 1.1 Mandate of the DPO
- Point of contact for the **Data Protection Board (DPB)** and for data principals.
- Owns the **DPIA programme** (incl. the employee-monitoring DPIA — see `dpia.md`).
- Owns the **lawful-basis mapping** to DPDP's closed legitimate-uses list (`lawful-basis-map.md`).
- Co-owns (with the CISO) the **breach-notification workflow** distinguishing a personal-data
  breach from a general cyber incident (`breach-notification.md`).
- Approves the **staff transparency notice** with HR/works-council (`transparency-notice.md`).
- Oversees **algorithmic due diligence** of the fraud models (DPDP algorithmic risk
  verification) jointly with the AI/Model Risk Committee.
- Commissions and reviews the **annual independent data-protection audit**.

### 1.2 Separation of duties
The DPO is deliberately **not** a builder, labeler, actor or administrator of the platform
(the four SoD personas, Part 19.6). This preserves independent oversight: the watcher of the
watchers is itself independent.

---

## 2. Annual independent data-protection audit — summary

> The audit is **scheduled for 2026-Q4** (per the seeded `dpia.audit_report` record). The
> summary below is the **template + planned scope** the independent auditor will report against;
> findings will be appended on completion and the record updated to reflect the audit outcome.

### 2.1 Scope of the audit
| Area | What the audit verifies |
|---|---|
| Lawful basis | Each processing activity maps to a valid DPDP legitimate use (closed list) and is documented (`lawful-basis-map.md`). |
| DPIA currency | The employee-monitoring DPIA is current, signed off (DPO-2026-004), and risks are mitigated as recorded. |
| Data minimization & retention | Collection is need-bound; purpose-bound retention timelines are enforced; lifecycle deletion is automated; erasure honoured with lawful carve-outs. |
| Cross-border transfer | Tokenize-before-egress + TEE attestation verified; destinations documented and not restricted jurisdictions; on-prem migration readiness assessed (Part 26.4). |
| Data-principal rights | Access/correction/erasure/grievance handled within SLA. |
| Algorithmic due diligence | Fairness audit current; protected attributes not used as features; explainability present; HITL natural-justice gate operative. |
| Breach readiness | DPB + affected-principal + CERT-In (6h) + RBI notification paths tested; PD-breach vs cyber-incident triage works. |
| Transparency | Staff notice published; works-council/union engagement evidenced; recourse channels live. |

### 2.2 Audit method
Independent auditor (external or 3rd-line Internal Audit, separate from the build/run teams):
documentation review, control walkthroughs, sample testing of access/unmask audit logs, a
breach-notification tabletop, and review of fairness-audit and model-validation evidence.

### 2.3 Reporting
The auditor reports to the **Board** (via the Audit Committee) with a rating per area and a
remediation plan with owners and SLAs. The DPO tracks remediation to closure and reflects the
outcome in the next DPIA cycle.

### 2.4 Audit result (to be completed 2026-Q4)
| Field | Value |
|---|---|
| Audit period | 2026-Q4 |
| Overall opinion | _Pending audit completion_ |
| Material findings | _Pending_ |
| Remediation status | _Pending_ |
| Next audit | 2027-Q4 (annual cadence) |

---

## 3. Cross-references
- Employee-monitoring DPIA + algorithmic due diligence: `governance/docs/dpia.md` (DPO-2026-004).
- Lawful-basis map: `governance/docs/lawful-basis-map.md`.
- Breach notification: `governance/docs/breach-notification.md`.
- Staff transparency & whistleblowing: `governance/docs/transparency-notice.md`.
- AI Policy: `governance/docs/ai-policy.md` (BR-2026-014).
