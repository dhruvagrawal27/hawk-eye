# Three Lines of Defense — Hawk-Eye (PLATFORM-39)

> Blueprint **Part 33.1** (team structure & the Three Lines of Defense).
> The Three-Lines model is the RBI-aligned governance backbone for a regulated bank's
> fraud-risk function. In Hawk-Eye it sits **on top of** the ALERT-ONLY guarantee: the
> platform scores and explains; the **1st line investigates and acts (request-block); a
> human in the approval gate decides**; the system never auto-blocks money (golden rule #1).

---

## 1. The model

The Three Lines of Defense separate **ownership of risk** (1st line) from **oversight of
risk** (2nd line) from **independent assurance over both** (3rd line). The lines must be
**organizationally independent** — the same person/team may not occupy two lines for the
same activity. This mirrors Hawk-Eye's in-software Separation-of-Duties personas
(`governance/rbac/route_guards.py`): **builder ≠ labeler ≠ actor ≠ administrator**, with
toxic-combination of two personas rejected at the route guard.

```
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                        BOARD / AUDIT COMMITTEE (SCBMF)                     │
   │                  ultimate accountability for fraud risk                    │
   └───────────────┬──────────────────┬───────────────────────┬───────────────┘
                   │                  │                       │
        ┌──────────┴───────┐ ┌────────┴─────────┐  ┌──────────┴───────────┐
        │  1st LINE         │ │  2nd LINE        │  │  3rd LINE            │
        │  OWN the risk     │ │  OVERSEE the risk│  │  ASSURE (independent)│
        │  Fraud / Vigilance│ │  Risk &          │  │  Internal Audit      │
        │  investigators    │ │  Compliance      │  │  (+ IS Audit, RBI)   │
        └──────────────────┘ └──────────────────┘  └──────────────────────┘
            triage + EDD +       thresholds, model       audits lines 1 & 2 +
            act on alerts        risk, FREE-AI gov,       the platform; reports
                                 DPDP/DPO                 to Audit Committee
```

---

## 2. 1st line — Fraud / Vigilance investigators (own the risk)

**Mandate:** detect, investigate, and act on insider/privileged-user fraud surfaced by
Hawk-Eye alerts.

| Responsibility | Hawk-Eye realization |
|---|---|
| Triage the alert queue (severity-routed) | L7 dashboard triage view; escalation matrix in `raci-matrix.md` / SOPs |
| Run **Enhanced Due Diligence (EDD)** | Per-typology SOPs in `sops/`; structured EDD checklist; explanation panel (SHAP / LAXCAT / graph evidence) |
| Decide escalation & request-block | `actor` persona; request-block routed to the **human approval (HITL) gate** — natural-justice before any classification |
| Capture disposition as a **label** | Every EDD outcome (fraud / FP / inconclusive) → immutable audit log → feedback loop (relabels L3/L4) |
| Refer onward | Handoff to **HR disciplinary** + **law-enforcement (CBI/ED)** per SOP enforcement chain |

**Roles:** Fraud Ops Lead (Responsible/Accountable for triage & block decision), Senior
Investigators, Investigators, Vigilance Officer.

**SoD persona:** `actor` — may act on alerts but may **not** build models, label training
data outside the EDD loop, or administer the platform.

---

## 3. 2nd line — Risk & Compliance (oversee the risk)

**Mandate:** set the policy and risk framework the 1st line operates within; provide
effective challenge; own model risk and FREE-AI governance.

| Responsibility | Hawk-Eye realization |
|---|---|
| EWS / RFA framework; thresholds & alert-volume governance | Rule/threshold change is **2nd-line owned** (Responsible: Compliance, Accountable: CRO) — see RACI |
| **Model risk management (SR 11-7)** | **Independent Model Validation Unit** — separate from ML Eng; effective challenge; seeded sign-off `MV-2026-007`, tier-1 |
| **FREE-AI governance** | 7 Sutras (Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience) + 6 pillars (Infrastructure, Policy, Capacity, Governance, Protection, Assurance); board AI policy `BR-2026-014` |
| Fairness / bias oversight | AI Ethics Committee review (seeded `ETH-2026-006`); disparate-impact by dept/grade |
| **DPDP / data protection** | India-resident **DPO**; employee-monitoring **DPIA** `DPO-2026-004`; lawful-basis mapping; proportionate monitoring |
| Regulatory reporting | CERT-In (6h), RBI Fraud MD 2024, RBI ITGRCA capacity (ITSC `ITSC-2026-009`) |

**Roles:** CRO/MLRO (Accountable for block decision, rule/threshold change), Model Risk
Management, Compliance, FREE-AI Governance lead, DPO.

**SoD persona:** governance/`labeler` oversight — sets policy and validates; does **not**
operate the alert queue (that is 1st line) and does **not** audit itself (that is 3rd line).

---

## 4. 3rd line — Internal Audit (independent assurance)

**Mandate:** independent, objective assurance over the design and operating effectiveness of
both the 1st and 2nd lines, and over the Hawk-Eye platform itself.

| Responsibility | Hawk-Eye realization |
|---|---|
| **IS audit per RBI ITGRCA 2023** | Audits PAM, RBAC/SoD, immutable audit log, capacity, BCP/DR |
| Audit model governance | Independent of ML Eng **and** of the 2nd-line validators; checks effective-challenge integrity |
| Audit the operating model | Checks RACI is followed, SOPs are applied, escalation/TAT (≤30-day) met |
| Evidence access | Read-only auditor role over the immutable WORM audit log and the seeded governance DB |

**Roles:** Chief Internal Auditor (reports to **Audit Committee / SCBMF**, not to CIO/CRO),
IS Audit team, model-audit liaison.

**SoD persona:** read-only auditor — may **inspect** everything, **change** nothing.

---

## 5. Independence rules (why the model holds)

1. **No line wears two hats** for the same activity — enforced organizationally (org chart)
   and in software (SoD route guards reject toxic-combinations).
2. **Validators ≠ builders** — the Model Validation Unit sits in 2nd-line Risk, never in ML
   Engineering (SR 11-7 effective challenge).
3. **Audit reports to the board**, not to management it audits (3rd-line independence).
4. **The platform never decides** — in all three lines, the ALERT-ONLY + HITL natural-justice
   gate is preserved; degradation to rules-only (Part 18) reduces sophistication, never the
   human-decides guarantee.

Cross-references: `org-chart.md` (structure), `committee-charters.md` (governance bodies),
`raci-matrix.md` (the six key activities), `sops/` (1st-line playbooks).
