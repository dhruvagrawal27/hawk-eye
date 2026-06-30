# Periodic Model-Risk Review — Hawk-Eye fusion-2026.2.0 (PLATFORM-23, MOCK)

> Blueprint **Part 13** (model-risk reviews) + **Part 27** (MRM, SR 11-7). **MOCK** evidence
> artifact tied to model version **fusion-2026.2.0**; wired to the governance DB
> (`security_reports` type=`model_risk`, status `passed`) and the AI/Model-Risk Committee record.

- **Review date:** 2026-05-02 · **Reviewer:** Model Risk Committee (independent of developers)
- **Risk tier:** Tier-1 (influences high-impact fraud triage) · **Result:** **PASSED** (3 minor findings, 0 critical)

## Effective-challenge dimensions (SR 11-7)
| Dimension | Finding |
|---|---|
| **Conceptual soundness** | Transparent weighted ensemble over auditable layer scores — explainable to audit (Part 18). |
| **Data** | Lineage verified; **temporal split** (no leakage); synthetic used for train/augment only, validated on labeled outcomes (Part 14). |
| **Performance** | PR-AUC 0.91; precision@k tuned to analyst capacity; **non-point-adjusted** time-series eval (Part 14 pitfall avoided). |
| **Stability** | PSI < 0.1 over 3-month backtest; drift monitors (Evidently/PSI) live. |
| **Outcomes** | Outcome analysis vs realized fraud confirms lift; MTTD reduced. |
| **LLM gateway** | Validated for **grounding/hallucination** (not just accuracy) — rejects narratives introducing facts not in evidence (Part 25.7). |

## Findings (minor)
1. Graph layer (L5) in shadow until more labeled collusion cases accrue — **accepted**, on roadmap.
2. Override-rate 18–29% — monitor for trust mis-calibration (operating_metrics, PLATFORM-39).
3. Credit/loan fraud is **slow-lane only** (honest limit, Part 12) — documented, not a defect.

## Feedback-loop & fairness (ML-specific, Part 27.3 / Part 29)
- EDD feedback loop monitored for bias amplification; label distributions reviewed.
- Fairness audit (disparate impact by dept/grade/region) **passed**, AI Ethics Committee 2026-04-21.

## Decision
Approved for production promotion **subject to** the independent-validation sign-off gate
(PLATFORM-34) — which is satisfied (MV-2026-007). Next review: quarterly or on drift trigger.
