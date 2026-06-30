# ML-Specific Independent Validation Scope (ML-23)

> Blueprint Part 27 (Model Risk Management). This document defines the **ML-specific**
> scope an *independent* validator (separate from the model developers) must cover for
> every model in the Hawk-Eye insider-fraud stack (L2–L6 scoring + the LLM narrative
> gateway), in addition to the standard MRM checks (conceptual soundness, data quality,
> performance, stability, outcomes).
>
> **ALERT-ONLY:** every model only raises alerts for human investigation — none auto-blocks
> a person. Validation must confirm this invariant holds end-to-end.
>
> Governance **process** mocks (board policy, committees, DPIA) are explicitly **out of
> scope here** — those are owned by the PLATFORM workstream. This file covers only the five
> ML-specific validation items.

## 1. Data drift
Validate that the model's input feature distributions are monitored for drift against a
reference window using **PSI** and the **KS** two-sample test (per-feature), and that a
**drift-crossing fires an off-cycle retrain trigger** (`ml.mlops.drift.RetrainTrigger`).
Confirm: reference/current windows are time-disjoint; PSI bands (0.1 moderate / 0.25
significant) and the KS α are sensible for the feature; Evidently is used where present with
a numpy PSI/KS fallback that always runs. Confirm drift alerts are advisory, never blocking.

## 2. Feedback-loop bias amplification
Validate that the EDD-disposition → retrain loop does **not** amplify bias: confirmation
rates are monitored **across protected groups** (`ml.fairness.feedback_trap`) so a group is
not disproportionately confirmed-as-fraud and then over-represented in the next training
set. Confirm the retrain consumes new labels honestly (time-split, never point-adjusted) and
that group label-distribution shifts trigger a correction rather than silent reinforcement.

## 3. Non-stationarity (concept drift / decay)
Validate that **concept drift** is measured as rolling precision/recall over time-ordered
dispositions (`ml.mlops.drift.rolling_precision_recall`) and that decay past a threshold is
caught and recommends a retrain (`ml.mlops.governance.monitoring`). Confirm thresholds are
recalibrated for non-stationary fraud typologies, baselines refresh on schedule, and the
champion/challenger promotion gate re-evaluates on a fresh time split (no stale eval set).

## 4. Explainability
Validate that every alert carries **reason codes** and a **narrative** that are faithful and
contestable (blueprint Part 29.2): TreeSHAP/attention/graph attributions for scoring layers,
the deterministic template or grounded LLM narrative for the gateway. Confirm explanations
are **cross-checked against rules + raw evidence** (they are adversarially manipulable), that
the LLM narrative is validated for **grounding/hallucination** (no fact absent from the
reason codes, no de-anonymisation of tokens), and that the model card lists known failure
modes and limitations.

## 5. Adversarial robustness
Validate the model against the blueprint Part 19.2 adversarial surface:
- **Evasion** — peer-relative baselines, hidden thresholds, randomized review sampling,
  diverse rules+unsup+sup+graph ensemble.
- **Poisoning** — train-set anomaly checks, change-point / peer-anchored baselines,
  label-distribution review, immutable label audit, provenance/lineage.
- **Inversion / membership** — internal-only authenticated rate-limited inference, no raw
  scores externally, regularization/DP, extraction-pattern monitoring.
- **Explanation manipulation** — prefer interpretable models + rule provenance; cross-check
  explanations vs rules and raw evidence.

Confirm the **signature is verified on model load** and that a **simulated metric regression
triggers automatic rollback** (`ml.mlops.promotion`), so a poisoned/degraded challenger
cannot silently take over from the champion.

---

### Tiering of validation depth
Higher **risk tier** ⇒ deeper validation + more frequent review (`ml.mlops.governance.risk_tiering`):
the L6 fusion meta-model and L3 supervised scorer (which most directly drive the
investigation decision) are **tier-1 critical**; the narrative LLM (explains, never decides)
is at most **tier-3 moderate**. The change → validation → approval → deploy workflow
(`ml.mlops.governance.change_workflow`) **gates deployment** on completion of the items above
plus an **independent approver** (not the change author) for tiers that require sign-off.
