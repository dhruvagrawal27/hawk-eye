# Org Chart — Hawk-Eye Operating Model (PLATFORM-39)

> Blueprint **Part 33.1** (team structure & the Three Lines of Defense).
> Hawk-Eye is **ALERT-ONLY**: every team below either *builds/runs* the scoring-and-
> explanation platform or *uses* its alerts — but **a human always decides; the system
> never auto-blocks money** (golden rule #1). Deploy target = AWS Lightsail, ap-south-1,
> data-residency in-india (ADR-0001; on-prem in-India is production).

This file describes two distinct populations:
1. **Build/run teams** — engineering + security functions that deliver and operate the
   platform (Part 33.1).
2. **Use teams** — the **Three Lines of Defense** that consume alerts and own risk
   (1st line Fraud/Vigilance, 2nd line Risk & Compliance, 3rd line Internal Audit).
   The line-by-line mapping lives in `three-lines-of-defense.md`; committee governance
   lives in `committee-charters.md`; who-does-what is in `raci-matrix.md`.

---

## 1. ASCII org chart

```
                          ┌───────────────────────────────────┐
                          │        BOARD OF DIRECTORS          │
                          │  (owns AI Policy BR-2026-014;      │
                          │   FREE-AI accountability)          │
                          └───────────────┬───────────────────┘
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            │                             │                             │
   ┌────────┴─────────┐        ┌──────────┴──────────┐       ┌──────────┴──────────┐
   │  IT Strategy     │        │  AI / Model-Risk    │       │  Audit Committee /  │
   │  Committee (ITSC)│        │  Committee (AMRC)   │       │  SCBMF (board fraud)│
   │  board-level     │        │  + AI Ethics Cttee  │       │                     │
   └────────┬─────────┘        │  + Info-Sec Cttee   │       └──────────┬──────────┘
            │                  └──────────┬──────────┘                  │
            │                             │                             │
   ════════ EXECUTIVE / SENIOR MANAGEMENT ═══════════════════════════════════════════
            │                             │                             │
   ┌────────┴─────────┐   ┌───────────────┴────────┐   ┌────────────────┴───────────┐
   │ CIO / Head of    │   │ CRO / MLRO             │   │ Chief Internal Auditor     │
   │ Technology       │   │ (Chief Risk Officer /  │   │ (CIA)                      │
   │                  │   │  Money-Laundering RO)  │   │                            │
   └────────┬─────────┘   └───────────┬────────────┘   └────────────────┬───────────┘
            │                         │                                 │
            │                  ┌──────┴───────┐                         │
            │                  │ CISO (Part 19)│ (dotted line to CIO    │
            │                  └──────┬───────┘  for ops, solid to CRO) │
            │                         │                                 │
 ──────── BUILD / RUN ───────  ───── USE: 1st & 2nd LINE ─────  ──── USE: 3rd LINE ────
            │                         │                                 │
  ┌─────────┴──────────┐    ┌─────────┴───────────┐         ┌───────────┴───────────┐
  │ ENGINEERING (build/run)│ │ Fraud / Vigilance   │         │ Internal Audit        │
  │                        │ │ (1st line)          │         │ (3rd line)            │
  │ ├ Platform / SRE       │ │ ├ Fraud Ops Lead    │         │ ├ IS Audit (RBI)      │
  │ ├ ML Engineering / DS  │ │ ├ Sr Investigators  │         │ ├ Model-audit liaison │
  │ ├ Data Engineering     │ │ ├ Investigators     │         │ └ Assurance reviewers │
  │ ├ Application Eng       │ │ └ Vigilance Officer │         └───────────────────────┘
  │ └ Security Eng (CISO)   │ │                     │
  └────────────────────────┘ │ Risk & Compliance   │
                             │ (2nd line)          │
                             │ ├ Model Risk Mgmt   │
                             │ ├ Compliance        │
                             │ ├ FREE-AI Governance│
                             │ └ DPO (data prot.)  │
                             └─────────────────────┘
```

> **SoD note.** The Independent Model Validation Unit (effective challenge, SR 11-7 /
> Part 22.4) reports through **2nd-line Risk**, NOT through Engineering — the people who
> **build** models must never **validate** them. This mirrors the in-software SoD personas
> (`governance/rbac/route_guards.py`): **builder ≠ labeler ≠ actor ≠ administrator** are
> disjoint and a toxic-combination of two is rejected.

---

## 2. Build / run teams (Part 33.1)

| Team | Owns | Key role(s) | Hawk-Eye artifacts |
|---|---|---|---|
| **Platform / SRE** | Runs the infra (Lightsail/on-prem), Kafka, DB, observability, on-call, DR/BCP. | SRE Lead, Platform Engineers | `services/*`, `deploy/*`, `ops/dr/*`, degradation switch |
| **ML Engineering / Data Science** | L3–L6 models + the **EDD feedback loop** (relabels L3/L4); model cards, drift. | ML Lead, Data Scientists, ML Engineers | `ml/*`, model registry |
| **Data Engineering** | Pipelines/integration; canonical actor→action→object schema; lineage, DQ SLAs. | Data Eng Lead, Pipeline Engineers | `data/*` |
| **Application Engineering** | L7 investigator dashboard, EDD capture, APIs (OpenAPI), entity-360. | App Eng Lead, Frontend/Backend Engineers | `frontend/*`, `backend/*` |
| **Security Engineering** | Part 19 — PAM, RBAC/SoD, secrets/HSM, VAPT, ATLAS red-team, SBOM, CERT-In wiring. | CISO, Security Engineers | `security/*`, `governance/rbac/*` |

> **Staffing of the *use* teams is volume-driven, not headcount-guessed.** The binding
> constraint is **alert volume the thresholds produce** (Part 14). Size the investigator
> team with the already-built **staffing calculator**
> (`tools/staffing-calculator/staffing_calculator.py`, Erlang-C + 3-shift roster — insider
> fraud is not 9–5). The seeded pilot plan: 120 alerts/day → **9 investigators across 3
> shifts**. Cost allocation/showback is the already-built **FinOps tool**
> (`tools/finops/finops.py`, Part 34.2). Do not re-derive these here — reference them.

---

## 3. Use teams — the Three Lines of Defense (Part 33.1)

| Line | Function | Owns | Maps to Hawk-Eye roles |
|---|---|---|---|
| **1st line** | **Fraud / Vigilance investigators** | Triage the alert queue; run **EDD**; decide escalation; act on alerts (request-block to the human approver). | `actor` persona; Fraud Ops Lead, Investigators, Vigilance Officer |
| **2nd line** | **Risk & Compliance** | EWS/RFA, thresholds, **model risk** (independent validation), **FREE-AI governance**, DPDP/DPO oversight. | `labeler`/governance personas; CRO/MLRO, Model Risk, Compliance, DPO |
| **3rd line** | **Internal Audit** | Independent assurance; **IS audit per RBI ITGRCA**; audits the other two lines and the platform. | Read-only auditor role; Chief Internal Auditor, IS Audit |

The full role-by-line mapping, including how the model preserves independence, is in
`three-lines-of-defense.md`.

---

## 4. Reporting & independence guarantees

- **CISO** reports to **CRO** for risk independence (solid line) with a dotted line to CIO
  for operations — the RBI-mandated Information Security Committee is chaired from Risk.
- **Independent Model Validation Unit** sits in 2nd-line Risk, separate from ML Engineering
  (the developers) — effective challenge per SR 11-7 (seeded sign-off `MV-2026-007`).
- **Internal Audit** reports to the **Audit Committee / SCBMF**, never to the CIO or CRO, so
  3rd-line assurance is independent of the functions it audits.
- **DPO** is India-resident and independent (seeded DPIA `DPO-2026-004`), advising both lines.

See `committee-charters.md` for the governance bodies these roles report into, and
`raci-matrix.md` for the six key activities and who is Responsible/Accountable.
