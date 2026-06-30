# Adoption & Change Management — Hawk-Eye (PLATFORM-39)

> Blueprint **Part 33.4** (adoption & change management — human factors) + **Part 14/19**
> (alert-fatigue) + **RBI ITGRCA** (DPDP/security training). Adoption is not a soft add-on:
> **alert fatigue is the #1 operational failure mode**, and mis-calibrated trust defeats the
> whole ALERT-ONLY design. This file defines the curriculum, the trust-calibration program,
> alert-fatigue discipline, and the feedback culture. Baselines = seeded `operating_metrics`
> (`override_rate` 0.18, `alert_fatigue` 0.32, period 2026-Q2).

---

## 1. Training curriculum

| Module | Audience | Content | Mandated by |
|---|---|---|---|
| **M1 — Tool fluency** | Investigators (1st line) | L7 dashboard, triage queue, entity-360, explanation panel, EDD checklist, disposition capture. | Operating model |
| **M2 — Interpreting AI output *and its limits*** | Investigators | What SHAP / LAXCAT attention / graph evidence mean; when **not** to trust a score; the ALERT-ONLY boundary (request-block ≠ block). | Part 33.4 |
| **M3 — Per-typology SOPs** | Investigators | Walk the `sops/` playbooks: beneficiary-fraud, exfiltration, privileged-DB-manipulation, collusion-ring, dormant-takeover — EDD steps, evidence, referral chain. | Part 33.3 |
| **M4 — DPDP & data protection** | All staff | DPDP Act 2023 + Rules 2025; employee-monitoring lawful basis & proportionality; data-principal rights; the system **watches staff** — handle accordingly. | **RBI ITGRCA** |
| **M5 — Security awareness** | All staff | RBAC/SoD personas, PAM, secrets hygiene, phishing, incident reporting, CERT-In 6h. | **RBI ITGRCA / Cyber 2016** |
| **M6 — Natural justice & due process** | Investigators, Fraud Ops Lead, HR | HITL gate, evidence standards, employee due-process before any classification; handoff to HR disciplinary + CBI/ED. | Part 29.2 / RBI |
| **M7 — FREE-AI 7 Sutras** | Risk, ML, leadership | Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience; the 6 pillars. | RBI FREE-AI 2025 |
| **M8 — Escalation & TAT** | Investigators | Severity routing; RBI ≤30-day examination TAT; SLA timers. | Part 33.3 |

**Refresh cadence:** annual for M4/M5 (ITGRCA), on every new typology for M3 (driven by
`sops/km-wiki.md`), on every model release for M2 (currently **fusion-2026.2.0**).

---

## 2. Trust calibration (override-rate program)

Analysts must **neither over-trust nor ignore** the AI. The explainability + feedback loop
builds *calibrated* trust; we measure it with **override rate**.

- **Signal:** `override_rate` (seeded 0.18). An override rate trending to **0** = blind
  over-trust (analysts rubber-stamp the model); trending to **1** = the model is being ignored
  (alert fatigue or distrust). Both are failures.
- **Target:** a *calibrated band*, ratified by Risk & Compliance (`raid-okr.md` KR3.1) — not a
  single number; the right band depends on precision@k and the typology mix.
- **Mechanism:** every override is a label. High-override typologies feed back into rule/L6
  tuning and the KM-wiki (`sops/km-wiki.md`) — closing the loop. Explanation quality (M2) is
  the lever that moves trust into the band.

---

## 3. Alert-fatigue management (operational discipline)

Treat fatigue as a first-class operational metric, not a vibe.

- **Signal:** `alert_fatigue` (seeded 0.32) + alert volume vs analyst capacity (Part 14).
- **The binding constraint is analyst capacity** — tune thresholds to the team's daily
  throughput (use `tools/staffing-calculator/`); **budget alerts, don't flood**.
- **Disciplines:** relentless threshold/rule tuning; suppress known-benign patterns;
  prioritize precision@k at the capacity-k; rotate shifts (insider fraud is not 9–5); monitor
  mean-time-to-disposition (`mttd` seeded 4.5). Fatigue is the **#1 operational failure mode**
  — a flooded queue means real fraud is missed.
- **Governance:** ISC/AMRC review fatigue + override trends; threshold changes go through the
  CAB (RACI 2.4).

---

## 4. Feedback culture (the training signal)

- Make EDD dispositions **easy and valued** — they are the engine of continuous improvement;
  every fraud/FP/inconclusive returns as a label that compounds detection quality.
- Celebrate dispositions and new-typology discoveries; the investigator who spots a novel
  pattern feeds it into rules + the synthetic red-team library via `sops/km-wiki.md`.
- Disposition completeness is an OKR (`raid-okr.md` KR3.3): ≥95% of alerts dispositioned
  within TAT. No silent queues.

---

## 5. Change management for releases

- New model release (e.g. fusion-2026.2.0) → M2 refresh + CAB change (`CAB-2026-033`) +
  rollback runbook; degradation switch verified before cutover.
- New typology → SOP added to `sops/` + M3 refresh + rule + synthetic-library update
  (KM-wiki loop) + Steering/RAID note.
- Threshold change → re-run staffing calculator; communicate expected volume shift to the
  shift roster before it lands.

Cross-references: `raid-okr.md` (the metrics & targets), `sops/` (the playbooks trained in M3),
`sops/km-wiki.md` (feedback loop into rules + synthetic library), `three-lines-of-defense.md`
(who is trained for which line).
