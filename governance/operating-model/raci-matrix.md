# RACI Matrix — Hawk-Eye Key Activities (PLATFORM-39)

> Blueprint **Part 33.2** (RACI, illustrative, for key activities).
> This file **reproduces the Part 33.2 table exactly** and then annotates each activity with
> its Hawk-Eye realization, SoD persona, and escalation. **R**esponsible (does the work),
> **A**ccountable (owns the outcome, one per row), **C**onsulted (two-way), **I**nformed
> (one-way). The ALERT-ONLY guarantee is preserved across every row: the system scores and
> explains; a **human decides**; it never auto-blocks money (golden rule #1).

---

## 1. RACI (reproduced exactly from Part 33.2)

| Activity | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Alert triage & EDD | Investigator | Fraud Ops Lead | ML Eng (explanations) | Compliance |
| Block decision | Fraud Ops Lead | CRO/MLRO | Legal | Business line |
| Model deploy | ML Engineer | Model Risk Committee | Validation, Security | Audit |
| Rule/threshold change | Compliance | CRO | Fraud Ops | Audit |
| Incident response | SRE/Security | CISO | Vendor, RBI/CERT-In liaison | Board |
| Fairness review | Data Science | AI Ethics Committee | HR, Legal | Board |

---

## 2. Activity annotations (Hawk-Eye realization)

### 2.1 Alert triage & EDD
- **Line:** 1st (Fraud/Vigilance). **SoD persona:** `actor`.
- **Realization:** Investigator works the severity-routed L7 queue, runs the per-typology SOP
  (`sops/`), consults ML Eng's explanation panel (SHAP / LAXCAT / graph). Disposition →
  immutable audit log → feedback loop. Compliance is **Informed** of patterns.
- **Escalation:** high-risk + high-exposure → Senior Investigator + Vigilance immediately.

### 2.2 Block decision
- **Line:** 1st owns the request; 2nd is accountable. **ALERT-ONLY checkpoint.**
- **Realization:** Fraud Ops Lead **requests** a block; it routes through the **HITL
  natural-justice gate**; **CRO/MLRO** is accountable for the human decision. Legal is
  **Consulted** (employee due-process); the business line is **Informed**. The platform never
  blocks autonomously.

### 2.3 Model deploy
- **Line:** build/run (ML Eng) executes; 2nd (Model Risk Committee) is accountable.
- **Realization:** ML Engineer (`builder` persona) deploys **only after** Independent
  Validation + Security are **Consulted** and AMRC approves. SoD: the builder may not also
  validate. Audit is **Informed**. Seeded: `MV-2026-007`, `AMRC-2026-012`, `CAB-2026-033`,
  model **fusion-2026.2.0**.

### 2.4 Rule/threshold change
- **Line:** 2nd (Risk & Compliance). **Binding constraint = analyst capacity (Part 14).**
- **Realization:** Compliance is Responsible; **CRO** accountable; **Fraud Ops Consulted**
  (they live the alert volume — use `tools/staffing-calculator/` to check the new threshold
  against capacity). Audit **Informed**. Changes flow through the CAB process.

### 2.5 Incident response
- **Line:** build/run (SRE/Security); CISO accountable.
- **Realization:** SRE/Security run the runbook; **Vendor + RBI/CERT-In liaison Consulted**
  (CERT-In **6-hour** reporting); **Board Informed**. Degradation switch to rules-only keeps
  alerting alive (Part 18). Seeded breach workflow `SEC-2026-021`.

### 2.6 Fairness review
- **Line:** Data Science runs it; AI Ethics Committee accountable.
- **Realization:** Data Science computes disparate-impact (by dept/grade); **HR + Legal
  Consulted** (this system watches staff); **Board Informed**. Seeded: Ethics minutes
  `2026-04-21`, approval `ETH-2026-006`; re-review every 6 months.

---

## 3. Cross-cutting accountability principles

- **One Accountable per row** — no diffusion of ownership.
- **SoD enforced in software** — builder/labeler/actor/administrator are disjoint
  (`governance/rbac/route_guards.py`); a person Accountable for one activity cannot quietly be
  Responsible for an incompatible one.
- **Validators ≠ builders** — for *Model deploy*, Validation is Consulted and the Model Risk
  Committee is Accountable, never the ML Engineer who built it (SR 11-7).
- **Audit is Informed, never Accountable** — 3rd line stays independent; it assures, it does
  not own operational outcomes.
- **ALERT-ONLY across all rows** — every "decision" row terminates at a human, never at the
  model.

Cross-references: `three-lines-of-defense.md` (line mapping), `committee-charters.md`
(the Accountable committees), `sops/` (the EDD playbooks behind row 2.1), `raid-okr.md`
(the OKRs these activities are measured against).
