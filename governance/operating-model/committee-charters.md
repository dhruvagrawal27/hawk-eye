# Committee Charters — Hawk-Eye Governance (PLATFORM-39)

> Blueprint **Part 33.1** (governance bodies) + **Part 27.2** (AI/Model-Risk Committee).
> **MOCK:** committee constitution is a human/legal act; the committee RECORDS (charter,
> members, minutes) are **seeded in the governance DB** (`committees`, `committee_members`,
> `committee_minutes` — `governance/db/seed.py`). These charters mirror those seeded records
> exactly; query them with the governance DB (`make seed-governance`).

Five governance bodies oversee Hawk-Eye. The first four are seeded in the DB; the fifth
(Audit Committee / SCBMF) is the board fraud committee from the original doc to which Internal
Audit (3rd line) reports.

| Committee | Type (DB) | Cadence (seeded) | Reports to | Charter (seeded) |
|---|---|---|---|---|
| **AI / Model-Risk Committee (AMRC)** | `ai_model_risk` | **monthly** | Board | Approves models, reviews incidents, reports to Board (Part 27.2). |
| **AI Ethics Committee** | `ethics` | **quarterly** | Board | Reviews fairness results, high-impact decisions, incidents (Part 29.2). |
| **Information Security Committee (ISC)** | `isc` | **monthly** | Board (via CRO) | RBI-mandated; chaired from Risk (Part 33.1). |
| **IT Strategy Committee (ITSC)** | `itsc` | **quarterly** | Board | Board-level; reviews annual capacity assessment (ITGRCA). |
| **Audit Committee / SCBMF** | board fraud | quarterly | Board | Fraud oversight; receives Internal Audit (3rd line) assurance. |

---

## 1. AI / Model-Risk Committee (AMRC)

- **Purpose.** The model-governance authority. Approves model promotion to production,
  reviews AI incidents, owns the model inventory + tiering, and reports model risk to the
  Board. The enforcement point for SR 11-7 and RBI FREE-AI model-risk expectations.
- **Membership (seeded).** Chair **Dr. R. Iyer** (risk); members **S. Banerjee** (compliance),
  **A. Khan** (business), **P. Rao** (tech). The Independent Model Validation Unit and Security
  are **Consulted** (RACI). 2nd-line body.
- **Cadence.** **Monthly** (seeded `cadence="monthly"`), plus ad-hoc for incidents.
- **Authority.** Approve / reject / condition model promotion; require re-validation; halt a
  model (kill-switch to rules-only fallback, Part 18). **Cannot** override the ALERT-ONLY
  guarantee or auto-block money.
- **Seeded evidence.** Minutes `2026-04-14`: *APPROVED promotion of fusion-2026.2.0 subject to
  independent validation sign-off*; promotion approval `AMRC-2026-012`; validation `MV-2026-007`
  (signed off `2026-04-30`); CAB change `CAB-2026-033`.
- **Model version under review:** **fusion-2026.2.0** (the go-live release).

## 2. AI Ethics Committee

- **Purpose.** Independent ethics oversight. Reviews fairness/bias audit results, high-impact
  automated decisions, and AI incidents through a FREE-AI **Fairness** + **People First** lens.
- **Membership (seeded).** Chair **Justice (Retd.) M. Nair** (independent); members
  **L. Fernandes** (HR), **G. Mehta** (legal). HR and Legal presence is deliberate — this
  system watches staff, so employee-fairness and natural justice are first-class concerns.
- **Cadence.** **Quarterly** (seeded `cadence="quarterly"`); fairness re-review every 6 months.
- **Authority.** Accept / reject fairness audits; mandate mitigations; escalate disparate
  impact to the Board. Is **Accountable** for the *Fairness review* activity in the RACI.
- **Seeded evidence.** Minutes `2026-04-21`: *Fairness audit ACCEPTED; no disparate flagging
  beyond risk-justified; re-review in 6 months*; approval `ETH-2026-006`.

## 3. Information Security Committee (ISC)

- **Purpose.** The RBI-mandated security governance body (RBI ITGRCA 2023 + Cyber 2016).
  Oversees the Part 19 security posture: PAM, RBAC/SoD, VAPT, ATLAS adversarial-ML red-team,
  SBOM, secrets/HSM, and incident response including **CERT-In 6-hour** reporting.
- **Membership.** Chaired **from Risk** (RBI requirement); CISO, Security Engineering, SRE
  Lead, and a Risk/Compliance representative. 2nd-line oversight of a build/run function.
- **Cadence.** **Monthly** (seeded `cadence="monthly"`).
- **Authority.** Approve the security baseline; accept/reject VAPT & red-team results; own the
  breach-notification workflow; trigger incident response. **Accountable: CISO** for *Incident
  response* (RACI).
- **Seeded evidence.** VAPT `2026-05-08` (0 critical), ATLAS red-team `2026-05-09` (0 critical),
  breach-notification policy `SEC-2026-021`, transparency notice `HR-2026-011`.

## 4. IT Strategy Committee (ITSC)

- **Purpose.** The board-level technology-strategy body (RBI ITGRCA). Owns the technology
  roadmap, the annual **capacity assessment**, and major architecture/vendor decisions
  (incl. ADR-0001 Lightsail deviation, vendor concentration risk for AWS + NEAR AI + Groq).
- **Membership.** Board-level: directors, CIO, CRO, CISO (in attendance).
- **Cadence.** **Quarterly** (seeded `cadence="quarterly"`).
- **Authority.** Approve the annual capacity assessment, the program roadmap and budget
  (steering function, Part 34.1), and major build-vs-buy / vendor decisions.
- **Seeded evidence.** Capacity assessment approval `ITSC-2026-009` (`2026-05-20`).

## 5. Audit Committee / SCBMF (board fraud committee)

- **Purpose.** The board fraud-oversight committee (the SCBMF / Special Committee for
  Monitoring & Follow-up of Fraud, from the original doc). Receives **Internal Audit (3rd
  line)** assurance, oversees fraud-MD reporting (RBI Fraud MD 2024), and is ultimately
  accountable for fraud risk.
- **Membership.** Independent directors; the **Chief Internal Auditor reports here** (not to
  CIO/CRO) to preserve 3rd-line independence.
- **Cadence.** Quarterly, plus on material fraud events.
- **Authority.** Direct independent investigations; receive IS-audit and model-audit findings;
  escalate to the Board and RBI. Independent of the functions it oversees.

---

## 6. Authority boundaries (what no committee may do)

- **No committee may auto-block money** — the ALERT-ONLY + HITL natural-justice gate is
  inviolable; only a human approver acts on a request-block.
- **No committee may collapse a line of defense** — independence (org chart + SoD route
  guards) is structural, not at any committee's discretion.
- **Escalation path:** AMRC / ISC / Ethics → Board; ITSC is already board-level; SCBMF →
  Board + RBI for material fraud. Cross-references: `three-lines-of-defense.md`,
  `raci-matrix.md` (who is Consulted/Informed per activity), `raid-okr.md` (RAID + OKRs the
  committees review).
