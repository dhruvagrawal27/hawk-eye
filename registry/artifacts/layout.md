# Model registry artifact layout (DATABASE-7)

> The **published path contract** ML packages into and BACKEND's serving loader
> verifies against. Blueprint **Part 23.1** (formats, l.855-858), **Part 23.2**
> (layout `{layer}/{model}/{version}/`, l.861).

## Object-store path (exact)
```
s3://models/{layer}/{model}/{version}/         # MinIO bucket `models` (object-locked, SSE, versioned)
    model.onnx                 # ONNX serving format (trees AND nets)
    booster.txt | model.cbm | model.joblib     # NATIVE booster (warm-start retrain)
    transform_chain/           # preprocessors / feature transformers (joblib), versioned WITH the model
        <step>.joblib
    calibrator.joblib          # probability calibrator (part of the chain)
    checkpoint.pt              # nets (L4/L5): PyTorch checkpoint (alongside model.onnx)
    metadata.json              # six-field reproducibility metadata (below)
    signature.sig              # detached signature over the whole bundle (DATABASE-8)
```
Example: `models/L3/lightgbm_gbdt/v1.4.2/` · `models/L4/laxcat/v0.3.0/` (with `checkpoint.pt`).

## Formats by model family (Part 23.1)
| Family | Serving | Retrain / native | Extra |
|---|---|---|---|
| Trees (L2/L3: LightGBM/XGBoost/CatBoost) | `model.onnx` | `booster.txt` / `model.cbm` / `model.joblib` | — |
| Nets (L4/L5: sequence/graph) | `model.onnx` | — | `checkpoint.pt` (PyTorch) |
| **All** | — | — | `transform_chain/` + `calibrator.joblib` versioned **together** |

> A model is **never just the estimator** — the preprocessors, feature
> transformers, and calibrator are versioned together as the whole transform chain
> (Part 23.1). `serializer.save_chain` / `load_chain` persist/reload the chain as a
> unit; an ONNX round-trip reconstructs identical predictions on a fixture vector.

## `metadata.json` — the six required fields (DATABASE-8, Part 23.2)
```json
{
  "dataset_hash": "sha256:…",          // lineage → Part 21.5 (+ feature_set_version)
  "params": { "num_leaves": 64, "...": "..." },
  "metrics": { "pr_auc": 0.91, "...": "..." },
  "training_code_commit": "9f34901",   // git SHA of the training code
  "approver": "EMP-co02",              // four-eyes sign-off (SoD: promoter != approver)
  "signature": "ed25519:…",            // hex of signature.sig (also stored as the file)
  "layer": "L3", "model": "lightgbm_gbdt", "version": "v1.4.2",
  "feature_set_version": "fs-2026.06", "stage": "Production"
}
```

## Stages (DATABASE-8, MLflow Model Registry, Part 23.2)
`Staging → Production → Archived`. Promotion is recorded (with approver, SoD
enforced) and emits an access-log audit event (DATABASE-6). Serving pulls
**Production**, verifies the signature, and records `model_version` per score
(Part 23.4; `hawkeye.scores.model_version`).

## Security (DATABASE-1/8, Part 23.3 / 19.2)
Encrypted at rest (SSE) · versioned + **object-lock** · least-privilege
(`models-writer`/`models-reader`) · **signature verified on load (reject on
tamper)** · every read/load/promote **access-logged** to the audit topic.
