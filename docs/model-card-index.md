# Model Card Index — Pointer

> **Owner:** PLATFORM (Laptop 06) maintains *this index* · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 17.A** (model-by-layer cheat sheet), **Part 20**
> (per-layer technique selection), **Part 25** (LLM gateway), **Part 27.2** (MRM inventory),
> **Part 34.3** (model cards as a required knowledge asset).
>
> **ML owns the real model cards.** This file is an **INDEX** only. The authoritative model cards
> are produced by the **ML** workstream from actual training runs (`ml/`, registered in MLflow,
> :5000). Each card's **independent-validation sign-off** is recorded in the **governance DB** and
> keyed to the model version under review: **`fusion-2026.2.0`**.

---

## The model inventory (L2–L6 + LLM gateway)

Per the blueprint's model-by-layer cheat sheet (Part 17.A) — each layer needs its own model card
(purpose, training data, metrics, limitations, fairness, owner, version):

| Layer | Job | Model(s) | Labels? | Card owner |
|---|---|---|---|---|
| **L1 — Rules / BRE** | Known typologies, SoD/toxic-combos | Deterministic rules / CEP (not an ML model — rule catalogue + change control) | No | PLATFORM/Compliance |
| **L2 — Unsupervised** | Cold-start novelty | Isolation Forest, Autoencoder, ECOD/COPOD (PyOD) | No | **ML** |
| **L3 — Supervised** | Precision event scorer | **XGBoost / LightGBM** + SHAP | Yes | **ML** |
| **L4 — Sequence** | Low-and-slow, sessions | USAD, TranAD, Anomaly-Transformer; **LAXCAT** (explainable) | Mixed | **ML** |
| **L5 — Graph** | Collusion / rings | GraphSAGE, GAT, hetero-GNN (PyG/DGL) | Semi | **ML** |
| **L6 — Fusion** | One calibrated 0–100 score + reasons | Stacked / weighted ensemble | Yes | **ML** |
| **LLM gateway** | Narrative *explanation only* (never a decision) | NEAR AI (primary) / Groq (secondary) / deterministic Jinja fallback; TEE-attested, tokenized | n/a | **ML** (gateway) + PLATFORM (TEE mock) |

> **L1 is rules, not ML** — it is documented in the rule catalogue and change-controlled (BACKEND.md
> §3 `/rules`, four-eyes + CAB). It is listed for completeness of the funnel L0..L6.

---

## Where the real cards live

| Asset | Location | Owner |
|---|---|---|
| **Per-layer model cards (the real ones)** | `ml/` + MLflow registry (:5000) | **ML** |
| **Model artifact format, score/reason-code payloads** | `ml/` (published contract) | **ML** |
| **Model-serving interface (ONNX/Triton, v2 protocol, :8001)** | `BACKEND.md` §6 | BACKEND / ML |
| **LLM gateway contract + audit memo fields** | `BACKEND.md` §7, blueprint Part 25 | BACKEND / ML |

---

## Governance: the validation record (MRM / SR 11-7)

Every model is a **regulated asset** (Part 16, Part 27). The card for each layer is tied to an
**independent-validation** sign-off in the governance DB, keyed to the model version:

- **Model version under review:** `fusion-2026.2.0`.
- **Validation record (seeded):** independent model-validation report at
  `governance/validation/out/model-validation-fusion-2026.2.0.md`, with a signed-off approval in
  the governance DB (`approvals`, `artifact_type = model_validation`). The go-live gate
  (`make go-live`) and the sign-off gate (`governance/validation/signoff_gate.py
  --model-version fusion-2026.2.0`) **block promotion** without it.
- **Surfaced to the dashboard** read-only via the **governance-api** (:8093) — see
  [`openapi-index.md`](./openapi-index.md).
- **SoD (Part 24.1):** whoever deploys a model **cannot** label data or close their own alerts;
  validation is **independent** of the builder.

> Every persisted score carries its `model_version` for reproducibility (BACKEND.md §6) — the
> audit trail can always reconstruct *which* model produced *which* alert.

---

## Per-card required contents (template the ML cards follow)

Each real ML card should cover: **purpose & layer** · **training data + dataset version**
(synthetic red-team library + EDD labels; Part 21) · **features used** · **metrics**
(PR-AUC / precision@k / recall-on-known-cases; **never** ROC-AUC alone — Part 14) · **calibration**
· **known limitations** (link [`honest-limits.md`](./honest-limits.md)) · **fairness/bias review**
(Part 29) · **explainability artifacts** (SHAP / rule provenance / attention) · **owner + version**
· **independent-validation reference** (governance DB).

---

*This is an index. The authoritative model cards are owned by **ML** and generated from real
training runs; their validation sign-offs live in the governance DB, keyed to `fusion-2026.2.0`.*
