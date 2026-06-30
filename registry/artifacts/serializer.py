"""Model file-format & transform-chain serializer (DATABASE-7).

Persists/reloads the **whole transform chain together** — a model is never just
the estimator, it is the entire (preprocessor → estimator → calibrator) chain
(blueprint Part 23.1 l.855-858). Exact object-store layout (Part 23.2 l.861):

    models/{layer}/{model}/{version}/
        model.onnx              # serving format (trees + nets)
        booster.txt|model.cbm|model.joblib   # native booster (warm-start retrain)
        transform_chain/        # preprocessors / feature transformers (joblib)
        calibrator.joblib       # probability calibrator (versioned WITH the model)
        checkpoint.pt           # nets (L4/L5) PyTorch checkpoint
        metadata.json           # six-field reproducibility metadata (DATABASE-8)
        signature.sig           # detached signature over the bundle (DATABASE-8)

The serializer is signing-agnostic (DATABASE-8 computes/verifies the signature and
passes the bytes in/out). It round-trips byte-for-byte, so reloaded ONNX produces
identical predictions on a fixture vector.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from registry.artifacts.store import ArtifactStore

# --- canonical filenames -----------------------------------------------------
ONNX = "model.onnx"
METADATA = "metadata.json"
SIGNATURE = "signature.sig"
CALIBRATOR = "calibrator.joblib"
CHECKPOINT = "checkpoint.pt"
TRANSFORM_CHAIN_DIR = "transform_chain"
# Recognised native booster filenames (trees keep the native format for warm-start).
NATIVE_BOOSTERS = ("booster.txt", "model.cbm", "model.joblib")

ARTIFACT_FILES = {
    "onnx": ONNX,
    "metadata": METADATA,
    "signature": SIGNATURE,
    "calibrator": CALIBRATOR,
    "checkpoint": CHECKPOINT,
    "transform_chain_dir": TRANSFORM_CHAIN_DIR,
    "native_boosters": NATIVE_BOOSTERS,
}


def registry_path(layer: str, model: str, version: str) -> str:
    """Relative path inside the `models` bucket: ``{layer}/{model}/{version}``."""
    return f"{layer}/{model}/{version}"


@dataclass
class ModelArtifact:
    """The whole transform chain for one model version."""

    layer: str
    model: str
    version: str
    onnx: Optional[bytes] = None
    native: Dict[str, bytes] = field(default_factory=dict)  # {"booster.txt": b"..."}
    transform_chain: Dict[str, bytes] = field(
        default_factory=dict
    )  # {"scaler.joblib": b"..."}
    calibrator: Optional[bytes] = None
    checkpoint: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: Optional[bytes] = None
    # Exact stored bytes of every signed file (populated by load_chain). Signature
    # verification uses THESE (what is actually on disk) rather than re-serializing
    # metadata — so a corrupt/invalid-JSON metadata.json still verifies (and fails)
    # instead of crashing the load before the audit log + signature check run.
    raw_files: Dict[str, bytes] = field(default_factory=dict)
    metadata_parse_error: bool = False

    @property
    def ref(self) -> str:
        return registry_path(self.layer, self.model, self.version)


def bundle_files(artifact: ModelArtifact) -> Dict[str, bytes]:
    """Signable bundle: every artifact file EXCEPT ``signature.sig``.

    Keys are relative to the version dir; deterministic JSON for ``metadata.json``
    so the bundle digest (DATABASE-8) is reproducible.
    """
    files: Dict[str, bytes] = {}
    if artifact.onnx is not None:
        files[ONNX] = artifact.onnx
    for name, data in sorted(artifact.native.items()):
        files[name] = data
    for name, data in sorted(artifact.transform_chain.items()):
        files[f"{TRANSFORM_CHAIN_DIR}/{name}"] = data
    if artifact.calibrator is not None:
        files[CALIBRATOR] = artifact.calibrator
    if artifact.checkpoint is not None:
        files[CHECKPOINT] = artifact.checkpoint
    files[METADATA] = json.dumps(
        artifact.metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return files


def save_chain(store: ArtifactStore, artifact: ModelArtifact) -> str:
    """Write the whole transform chain to ``{layer}/{model}/{version}/``.

    Writes ``signature.sig`` too if the artifact carries a signature. Returns the
    registry ref (``{layer}/{model}/{version}``).
    """
    base = artifact.ref
    for rel, data in bundle_files(artifact).items():
        store.put(f"{base}/{rel}", data)
    if artifact.signature is not None:
        store.put(f"{base}/{SIGNATURE}", artifact.signature)
    return base


def load_chain(
    store: ArtifactStore, layer: str, model: str, version: str
) -> ModelArtifact:
    """Reload the whole transform chain from the object store."""
    base = registry_path(layer, model, version)
    keys = store.list(base)
    art = ModelArtifact(layer=layer, model=model, version=version)
    for key in keys:
        rel = key[len(base) + 1 :]  # strip "{base}/"
        data = store.get(key)
        if rel != SIGNATURE:
            # keep the EXACT stored bytes for signature verification (every file
            # except the detached signature itself)
            art.raw_files[rel] = data
        if rel == ONNX:
            art.onnx = data
        elif rel == METADATA:
            try:
                art.metadata = json.loads(data)
            except (ValueError, TypeError):
                # corrupt/invalid-JSON metadata: do NOT crash the load — keep the
                # raw bytes (so signature verification still runs over them and
                # fails) and flag the parse error for callers.
                art.metadata = {}
                art.metadata_parse_error = True
        elif rel == SIGNATURE:
            art.signature = data
        elif rel == CALIBRATOR:
            art.calibrator = data
        elif rel == CHECKPOINT:
            art.checkpoint = data
        elif rel.startswith(TRANSFORM_CHAIN_DIR + "/"):
            art.transform_chain[rel.split("/", 1)[1]] = data
        elif rel in NATIVE_BOOSTERS:
            art.native[rel] = data
        # unknown extras are ignored (forward-compatible)
    return art


def verification_files(artifact: ModelArtifact) -> Dict[str, bytes]:
    """Bytes the signature is verified against.

    A loaded artifact verifies against the EXACT stored bytes (``raw_files``); a
    freshly-built in-memory artifact (pre-save) falls back to ``bundle_files``.
    This makes verification robust to a corrupt metadata.json (raw bytes preserved)
    and independent of JSON re-serialization quirks.
    """
    return dict(artifact.raw_files) if artifact.raw_files else bundle_files(artifact)


def list_versions(store: ArtifactStore, layer: str, model: str) -> List[str]:
    """List the versions present for a model (distinct ``{version}`` dirs)."""
    prefix = f"{layer}/{model}"
    versions = set()
    for key in store.list(prefix):
        rest = key[len(prefix) + 1 :]
        if "/" in rest:
            versions.add(rest.split("/", 1)[0])
    return sorted(versions)
