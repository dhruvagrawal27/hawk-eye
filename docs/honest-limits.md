# Honest Limits — what Hawk-Eye does *not* solve (and where it stops short)

> **Owner:** PLATFORM (Laptop 06) · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 12** ("The honest limits") + **Part 15** (Risks,
> pitfalls & honest limitations).
> **Purpose.** State the limits *plainly*, to stakeholders, regulators, and the board, so no
> one over-trusts the system. This file is the deliberate counterweight to
> [`detection-coverage-map.md`](./detection-coverage-map.md). **We do not oversell.**

Hawk-Eye dramatically raises detection speed and coverage for **digitally-observable** insider
and privileged-user fraud, and it gives investigators a unified, explainable, prioritized view.
It **complements — it does not replace** — tips, audit, segregation of duties, and culture. The
"no silver bullet" truth is set with leadership *explicitly*. (Part 15, "The 'no silver bullet'
truth".)

---

## 1. The three Part-12 honest limits (state these to stakeholders)

### 1.1 Credit/loan fraud is **slow-lane only**
Ghost/insider loans, inflated appraisals, and disbursement-to-non-sanctioned-account surface
**over weeks/months** via entity and document signals feeding the **EWS** (Early-Warning-Signal)
engine — they are **not a real-time win**. Hawk-Eye **accelerates** this work
(forensic-audit-in-*years* → red-flag-in-*weeks*) but **does not make it instant**. The slow lane
feeds RBI **EWS / Red-Flagged-Account (RFA) / CRILC / FMR**; it is an acceleration of the
existing supervisory machinery, not a replacement for credit underwriting controls.

### 1.2 Executive override / pure human collusion is **only partially** addressable
Executive financial-statement fraud, "the CEO overrides the control", and **pure human collusion
with no digital footprint** are only **partially** addressable by ***any*** system. The
technical signals we *can* offer are weak proxies (always-hits-target, close-control overrides,
cultural KRIs). These cases **still need** culture, whistleblowing, surprise audit, and board
oversight (the reference document's point, and the ACFE's). **Don't oversell this.**

### 1.3 A determined low-and-slow insider can still drift a baseline
A patient insider who knows they are watched can **shift a behavioural baseline gradually** so
each step looks normal. This is **mitigated — not eliminated** — by peer-anchoring (peer-relative,
not absolute, baselines), long observation windows, and change-point detection. We claim
*mitigation*, never *immunity*.

---

## 2. The Part-15 risks, pitfalls & honest limitations

These are the operating risks that come with the system; each is stated with its mitigation, and
none of the mitigations is claimed as a *cure*.

| Risk / limitation | Why it bites | Mitigation (mitigates, not eliminates) |
|---|---|---|
| **Adversarial insiders who know the thresholds** | They tune their behaviour to sit just under a fixed line | Don't expose logic; **peer-relative** (not absolute) baselines; controlled randomization of review sampling; emphasize unsupervised novelty detection |
| **Low-and-slow baseline poisoning** | Gradual drift normalises the abnormal | Long observation windows; **peer-group anchoring**; change-point detection; periodic baseline resets reviewed by humans |
| **Alert fatigue** | The **#1 operational killer** of fraud systems | **L6 fusion** (one alert per entity), rank by exposure, alert budgeting, feedback-loop precision tuning. Design against it from day one |
| **Privacy, employee surveillance & fairness** | The system **watches staff** — a legal/cultural problem if mishandled, not just technical | **Proportionality** (risk-relevant signals only, not everything); transparency with staff/works-council/HR/legal; fairness testing; strict RBAC; **human-in-the-loop with natural justice** before any classification |
| **Collusion & executive override remain partly out of reach** | No model fully solves "two honest-looking people defeating dual control" or "the CEO overrides the control" | Pair with human controls — whistleblowing, surprise audit, board oversight |
| **Cold start** | No labels on day one | Rules + synthetic + transfer-learning carry the first months; the feedback loop does the rest |
| **Model risk & explainability for regulators** | ML models are regulated assets | Governance, calibration, retained explanation artifacts, **independent validation** (MRM/SR 11-7) |
| **The "no silver bullet" truth** | Raises detection speed/coverage hugely — but for *digitally-observable* fraud only | **Complements, not replaces**, tips, audit, SoD, and culture. Set that expectation with leadership explicitly |

---

## 3. Evaluation honesty (so the metrics don't lie) — Part 14

Even our *measurement* is constrained, and we say so:

- **PR-AUC / average precision**, **precision@k**, **alert-to-true-fraud ratio**, and **recall on
  known historical cases** — not ROC-AUC alone (it flatters imbalanced data).
- **Pitfalls we actively avoid:** point-adjust inflation on time-series metrics; **data leakage**
  (e.g. PaySim balance columns); **temporal leakage** (always split train/test by *time*,
  past→future); and **synthetic-only evaluation** — synthetic is for training/augmentation;
  detection quality must be validated against *real* labelled outcomes.

---

## 4. The one-line version (for the board pack)

> Hawk-Eye **collapses detection time** and gives investigators superpowers for **digitally-
> observable** insider fraud. It is **alert-only** — a human decides. Credit fraud is
> **accelerated, not instantaneous**; executive override and footprint-free collusion are
> **only partially** in reach; a patient low-and-slow insider is **mitigated, not eliminated**.
> It **complements** — it does **not** replace — tips, audit, segregation of duties, and culture.

---

*Source of truth: blueprint Part 12 ("The honest limits") and Part 15 ("Risks, pitfalls & honest
limitations"). Read alongside [`detection-coverage-map.md`](./detection-coverage-map.md).*
