# Hawk-Eye ML Phasing (Blueprint Part 13 -> ML tasks)

This document maps the four delivery phases from blueprint **Part 13 (Phasing)**
to the concrete ML workstream tasks (`ML-*`) that deliver them. The sequencing
follows the blueprint's escalation rule (Part 7): ship rules + unsupervised +
dashboard first, add supervised once labels exist, and add sequence/graph models
only when they are justified under honest (non-point-adjust) evaluation.

Each phase below lists its **goal**, the **ML tasks** that deliver it, and the
**exit criteria** that must be met before moving on.

---

## Phase 1 — Baselines, unsupervised detection, capture loop

**Goal.** Stand up per-entity and per-peer behavioural baselines, the L2
unsupervised detector ensemble (Isolation Forest + Autoencoder via PyOD),
Enhanced Due Diligence (EDD) disposition capture, and the first detection
metric (precision@k). This is the minimum that produces actionable, ranked
alerts with no labels required.

**ML tasks delivering Phase 1:**

- **ML-1** — Foundation contracts / interfaces (`ml/base`), adapters
  (`ml/adapters`) exposing the DATA feature surface (per-entity / per-peer
  baselines with time decay).
- **ML-2** — Honest evaluation harness (`ml/eval`): time splits, leakage
  guards, **precision@k** and PR-AUC/AP (never ROC-AUC alone, never
  point-adjust).
- **ML-L2** — L2 unsupervised ensemble (`ml/layers/l2`): Isolation Forest
  (`n_estimators=150`, `max_samples=256`), ECOD/COPOD, Autoencoder with
  per-feature reconstruction-error explanation; fit on a NORMAL window, persist
  baselines + 99th-percentile thresholds.
- **ML-EDD** — EDD disposition capture into a labelled store (feeds Phase 2+
  supervised training and the active-learning loop in Phase 4).
- **ML-29** — Operational metric: precision@k surfaced on the ops dashboard
  alongside alert-volume-vs-capacity (this module).

**Exit criteria.** L2 ensemble produces ranked alerts; per-entity/per-peer
baselines persisted with thresholds; precision@k reported on a time-split eval;
EDD dispositions flowing into the labelled store.

---

## Phase 2 — Supervised scoring, explanations, calibration

**Goal.** Once Phase 1 labels accumulate, add the L3 supervised GBDT scorer with
SHAP reason codes, threshold tuning, and probability calibration.

**ML tasks delivering Phase 2:**

- **ML-L3** — L3 supervised scorers (`ml/layers/l3`): LightGBM (default),
  CatBoost (high-cardinality/imbalance), XGBoost (robust). Split by TIME, never
  random; class weights / `scale_pos_weight` + 1:3–1:10 negative subsample.
- **ML-SHAP** — TreeSHAP live reason codes (exact/fast on the hot path);
  interaction values OFFLINE only.
- **ML-THRESH** — Threshold tuning against the operating point (precision@k /
  alert-volume-vs-capacity trade-off).
- **ML-CAL** — Isotonic / Platt calibration so scores are real probabilities.
- **ML-L6** — L6 fusion (`ml/layers/l6`): stacked meta-learner over per-layer
  scores + rule flags, isotonic calibrated to 0–100 with severity × confidence
  and reason codes.

**Exit criteria.** L3 GBDT registered with AUPRC / Rec@K on a time-aware CV;
calibrated probabilities; SHAP reason codes attached to every alert; L6 fusion
emitting 0–100 risk with severity and confidence.

---

## Phase 3 — Sequence, graph, slow-lane, governance, drift

**Goal.** Add the deeper L4 sequence and L5 graph models (only where they beat
simple baselines under non-point-adjust eval), the slow-lane batch typologies,
model governance, and drift monitoring.

**ML tasks delivering Phase 3:**

- **ML-L4** — L4 sequence models (`ml/layers/l4`): simple baselines FIRST
  (windowed PCA / windowed IF / matrix-profile / small LSTM-AE), then
  **USAD / TranAD** and explainable supervised **LAXCAT** (CNN +
  variable-attention + temporal-attention). Range/affiliation-aware PR or
  VUS-PR; **NEVER point-adjust**; keep deep only if it beats baselines.
- **ML-L5** — L5 graph models (`ml/layers/l5`): **XGB-Graph / RF-Graph default**
  (k-hop aggregates -> GBDT), GraphSAGE (inductive), CARE-GNN / PC-GNN / BWGNN
  for camouflage/heterophily; GNNExplainer attribution; PyG / DGL / PyGOD.
- **ML-SLOW** — Slow-lane batch detectors for the SLOW typologies (fake_vendor,
  ghost_employee_payroll, alert_suppression, ghost_loan_appraisal), run on a
  daily/weekly cadence off the hot path.
- **ML-GOV** — Governance: MLflow registry (version + training-data hash +
  features + metrics + approving reviewer), model cards, independent validation
  sign-off before Production.
- **ML-DRIFT** — Drift monitoring (Evidently / PSI) triggering off-cycle
  retrain; data-integrity and stability checks.

**Exit criteria.** L4/L5 models registered and shown to beat baselines under
honest eval (or explicitly dropped); slow-lane typologies covered; MLflow
registry + model cards populated; drift monitors live.

---

## Phase 4 — Active learning, red-team, model-risk reviews

**Goal.** Close the loop: active-learning retrain cadence, red-team synthetic
typology library, and recurring model-risk management reviews.

**ML tasks delivering Phase 4:**

- **ML-AL** — Active-learning cadence: query uncertain / high-value cases first
  from EDD dispositions; scheduled retrain -> shadow -> champion/challenger ->
  canary with auto-rollback.
- **ML-REDTEAM** — Red-team synthetic typologies: behavioural / metamorphic /
  directional test library (known fraud scores high, benign low; amount-scaling
  must not decrease risk; off-hours + new-beneficiary + high-value raises risk
  monotonically); fairness GATED tests.
- **ML-MRM** — Model-risk management reviews (Part 27): model inventory + risk
  tiering, independent validation (conceptual soundness, data, performance,
  stability, outcomes; LLM grounding/hallucination), monitoring vs realized
  fraud, governed retirement.

**Exit criteria.** Active-learning retrain loop running on a cadence; red-team
library gating CI (build fails on disparate-impact breach or regression on the
fixed eval set); periodic MRM reviews scheduled with sign-off recorded.

---

## Cross-phase metrics (ML-29)

The operational and business metrics in `ml/metrics/ops.py` are reported across
all phases (blueprint Part 14):

- **Operational:** alert-volume-vs-capacity, mean-time-to-detection (MTTD),
  mean-time-to-disposition, false-positive rate, **RBI ≤30-day TAT compliance**.
- **Business:** estimated loss avoided, cases surfaced by system vs tips.
- **Detection** (in `ml/eval`): PR-AUC / AP, precision@k, alert-to-true ratio,
  recall on known cases, time-to-detection reduction.
