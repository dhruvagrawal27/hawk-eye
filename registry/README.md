# `registry/` — Signed model-file registry (DATABASE-7/8)

> **Owner:** DATABASE owns the object-store + registry **layout, buckets,
> encryption, object-lock, signing-at-rest, signature-verify-on-load, and access
> logging**. **ML** owns the MLflow *tracking-server runtime* + the ONNX
> packaging/signing during training. We consume ML's artifacts and expose the
> layout + verification utilities ML & BACKEND call.
> Blueprint **Part 23** (formats/layout/security/serving) + **Part 19.2**
> (encrypted+signed+access-controlled+access-logged registry).

## Modules
| Path | Task | Purpose |
|---|---|---|
| `artifacts/layout.md` | DATABASE-7 | The exact `{layer}/{model}/{version}/` path + format contract (published) |
| `artifacts/serializer.py` | DATABASE-7 | `save_chain`/`load_chain` — persist/reload the **whole transform chain** |
| `artifacts/store.py` | DATABASE-7 | Object store (local FS / MinIO object-lock `models` bucket) |
| `mlflow/signing.py` | DATABASE-8 | Ed25519 detached signature over the bundle digest |
| `mlflow/load_verify.py` | DATABASE-8 | `secure_load` — verify-on-load, **reject on tamper** |
| `mlflow/access_log.py` | DATABASE-8 | Emit every read/load/promote/register → audit topic (DATABASE-6) |
| `mlflow/config.py` | DATABASE-8 | `Registry` facade: register (six-field meta+sign) · promote (SoD) · load |

## Contract (published in CONTEXT.md so ML packages into it)
- **Path:** `models/{layer}/{model}/{version}/` (e.g. `models/L3/lightgbm_gbdt/v1.4.2/`).
- **Files:** `model.onnx`, native booster (`booster.txt`/`model.cbm`/`model.joblib`),
  `transform_chain/`, `calibrator.joblib`, `checkpoint.pt` (nets), `metadata.json`,
  `signature.sig`.
- **metadata.json six fields:** `dataset_hash`, `params`, `metrics`,
  `training_code_commit`, `approver`, `signature` (detached pointer; authoritative
  signature is `signature.sig`). Plus `layer/model/version/feature_set_version/stage`.
- **Signature:** Ed25519 over the SHA-256 manifest of every file except
  `signature.sig`. Tampering with any file (onnx/native/transform/calibrator/
  metadata) invalidates it → load rejected.
- **Stages:** `Staging → Production → Archived`. Promotion records four-eyes/SoD
  (promoter ≠ approver) + emits an audit event.

## Quick use
```python
from registry.mlflow.config import Registry
from registry.artifacts.serializer import ModelArtifact

reg = Registry()  # local FS + WORM/Kafka emitter chosen from env
ref = reg.register(
    ModelArtifact(layer="L3", model="lightgbm_gbdt", version="v1.4.2",
                  onnx=onnx_bytes, native={"booster.txt": booster},
                  transform_chain={"scaler.joblib": scaler}, calibrator=calib),
    dataset_hash="sha256:…", params={...}, metrics={...},
    training_code_commit="9f34901", approver="EMP-co02")
reg.promote("L3", "lightgbm_gbdt", "v1.4.2", "Production",
            promoter="EMP-me01", approver="EMP-co02")        # SoD enforced
artifact = reg.load("L3", "lightgbm_gbdt", "v1.4.2")          # verify-on-load + access-log
```

## Security (DATABASE-1 buckets)
`models` bucket: SSE encrypted-at-rest · versioned · **object-lock** ·
least-privilege (`models-writer` ML packaging, `models-reader` serving load).
Every load/read/promote is **access-logged** to the WORM trail (extraction-theft
mitigation, Part 19.2). The serving loader (BACKEND `serving/loader.py`) calls
`secure_load`; unsigned/tampered artifacts are rejected (BACKEND.md §6a).
