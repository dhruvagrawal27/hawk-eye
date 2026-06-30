"""Reproducibility + lineage (ML-17; blueprint Part 22.4).

Every score the platform emits must be RECONSTRUCTABLE: given the persisted feature
vector + the model version, you can re-run the model and get the same number. That
requires:

* fixed seeds (delegated to :func:`ml.config.seed_everything`),
* a stable hash of the *dataset* and of the *feature schema* used to train,
* MLflow tracking when present (else a local JSON run record),
* and a ``ScoreRecord`` that stores the exact feature vector + model_version per score.

Nothing here imports a heavy model library, so it loads in any process (torch or
LightGBM) without the macOS dual-libomp hazard.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml._optional import HAS_MLFLOW, optional_import
from ml.config.seeds import GLOBAL_SEED, seed_everything

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_REPRO_ROOT = os.path.join(REPO_ROOT, "ml", "_artifacts", "repro")


# --------------------------------------------------------------------------- #
# hashing                                                                      #
# --------------------------------------------------------------------------- #
def _stable_bytes(obj: Any) -> bytes:
    if isinstance(obj, pd.DataFrame):
        # Hash the values + column order + dtypes; index is intentionally ignored so
        # a re-loaded-from-disk frame hashes the same as the in-memory one.
        cols = ",".join(str(c) for c in obj.columns)
        dtypes = ",".join(str(t) for t in obj.dtypes)
        try:
            vals = pd.util.hash_pandas_object(obj, index=False).to_numpy().tobytes()
        except Exception:
            vals = np.ascontiguousarray(obj.to_numpy(dtype=object).astype(str)).tobytes()
        return cols.encode() + b"|" + dtypes.encode() + b"|" + vals
    if isinstance(obj, pd.Series):
        return _stable_bytes(obj.to_frame())
    if isinstance(obj, np.ndarray):
        return np.ascontiguousarray(obj).tobytes()
    return json.dumps(obj, sort_keys=True, default=str).encode()


def dataset_hash(*objs: Any) -> str:
    """Deterministic SHA256 over one or more dataset objects (frames/arrays/dicts)."""
    h = hashlib.sha256()
    for o in objs:
        h.update(_stable_bytes(o))
        h.update(b"\x00")
    return h.hexdigest()


def feature_hash(columns: Any) -> str:
    """Hash of the ordered feature schema (column names) — the train/serve contract."""
    names = [str(c) for c in columns]
    return hashlib.sha256("|".join(names).encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# score record (the reconstructability contract)                              #
# --------------------------------------------------------------------------- #
@dataclass
class ScoreRecord:
    """A single persisted score + everything needed to reconstruct it."""

    entity_id: str
    score: float
    model_version: str
    feature_names: list[str]
    feature_vector: list[float]
    layer: str = "L0"
    dataset_hash: Optional[str] = None
    feature_hash: Optional[str] = None
    seed: int = GLOBAL_SEED
    ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts or time.time()
        return d

    def as_frame(self) -> pd.DataFrame:
        """Reconstruct the exact 1-row feature frame this score was produced from."""
        return pd.DataFrame([self.feature_vector], columns=self.feature_names)


class ScoreLedger:
    """Append-only JSONL ledger of ScoreRecords (persist feature vector + version)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.path.join(DEFAULT_REPRO_ROOT, "scores.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def record(self, rec: ScoreRecord) -> ScoreRecord:
        if not rec.ts:
            rec.ts = time.time()
        with open(self.path, "a") as fh:
            fh.write(json.dumps(rec.to_dict()) + "\n")
        return rec

    def record_batch(
        self,
        scorer: Any,
        X: pd.DataFrame,
        *,
        layer: str,
        dset_hash: Optional[str] = None,
    ) -> list[ScoreRecord]:
        """Score X and persist one ScoreRecord per row (feature vector + model_version)."""
        proba = _score_any(scorer, X)
        cols = [str(c) for c in X.columns]
        fh = feature_hash(cols)
        mv = getattr(scorer, "model_version", "unknown")
        out: list[ScoreRecord] = []
        for i, (idx, row) in enumerate(X.iterrows()):
            rec = ScoreRecord(
                entity_id=str(idx),
                score=float(proba[i]),
                model_version=mv,
                feature_names=cols,
                feature_vector=[float(v) for v in row.to_numpy(dtype=float)],
                layer=layer,
                dataset_hash=dset_hash,
                feature_hash=fh,
            )
            out.append(self.record(rec))
        return out

    def records(self) -> list[ScoreRecord]:
        if not os.path.isfile(self.path):
            return []
        out = []
        with open(self.path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(ScoreRecord(**json.loads(line)))
        return out


def reconstruct_score(rec: ScoreRecord, scorer: Any) -> float:
    """Re-run ``scorer`` on the persisted feature vector; should reproduce ``rec.score``."""
    p = _score_any(scorer, rec.as_frame())
    return float(np.asarray(p).ravel()[0])


def _score_any(scorer: Any, X: pd.DataFrame) -> np.ndarray:
    if hasattr(scorer, "predict_proba"):
        p = scorer.predict_proba(X)
    elif hasattr(scorer, "score_samples"):
        p = scorer.score_samples(X)
    else:
        raise TypeError("scorer must expose predict_proba or score_samples")
    return np.asarray(p, dtype=float).ravel()


# --------------------------------------------------------------------------- #
# run records + MLflow tracking                                               #
# --------------------------------------------------------------------------- #
@dataclass
class RunRecord:
    """A registered training run (mirrors what MLflow stores; local JSON fallback)."""

    run_id: str
    layer: str
    model_version: str
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)
    dataset_hash: Optional[str] = None
    feature_hash: Optional[str] = None
    feature_names: list[str] = field(default_factory=list)
    seed: int = GLOBAL_SEED
    calibrated: bool = False
    backend: str = "local"
    artifact_path: Optional[str] = None
    ts: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts or time.time()
        return d


class ReproTracker:
    """MLflow tracking when present, else a local JSON run store (always works)."""

    def __init__(self, *, experiment: str = "hawkeye-ml", root: Optional[str] = None,
                 use_mlflow: Optional[bool] = None) -> None:
        self.experiment = experiment
        self.root = root or DEFAULT_REPRO_ROOT
        os.makedirs(self.root, exist_ok=True)
        # Allow tests / CI to force the local backend even when mlflow is importable.
        self.use_mlflow = HAS_MLFLOW if use_mlflow is None else (use_mlflow and HAS_MLFLOW)
        self.backend = "mlflow" if self.use_mlflow else "local"

    def log_run(self, rec: RunRecord) -> RunRecord:
        rec.backend = self.backend
        if not rec.ts:
            rec.ts = time.time()
        self._log_local(rec)  # always keep a local copy for offline reconstruction
        if self.use_mlflow:
            try:
                self._log_mlflow(rec)
            except Exception:
                # MLflow misconfiguration must never fail a training run.
                rec.backend = "local"
        return rec

    def _log_local(self, rec: RunRecord) -> None:
        path = os.path.join(self.root, "runs.jsonl")
        with open(path, "a") as fh:
            fh.write(json.dumps(rec.to_dict()) + "\n")

    def _log_mlflow(self, rec: RunRecord) -> None:
        mlflow = optional_import("mlflow")
        if mlflow is None:  # pragma: no cover - guarded by use_mlflow
            return
        tracking_dir = os.path.join(self.root, "mlruns")
        os.makedirs(tracking_dir, exist_ok=True)
        mlflow.set_tracking_uri(f"file:{tracking_dir}")
        mlflow.set_experiment(self.experiment)
        with mlflow.start_run(run_name=rec.run_id):
            mlflow.set_tags({
                "layer": rec.layer,
                "model_version": rec.model_version,
                "dataset_hash": rec.dataset_hash or "",
                "feature_hash": rec.feature_hash or "",
                "calibrated": str(rec.calibrated),
            })
            mlflow.log_params({k: str(v) for k, v in rec.params.items()})
            mlflow.log_metrics({k: float(v) for k, v in rec.metrics.items()
                                if v is not None and np.isfinite(v)})

    def runs(self) -> list[dict[str, Any]]:
        path = os.path.join(self.root, "runs.jsonl")
        if not os.path.isfile(path):
            return []
        out = []
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


def fixed_seed(seed: int = GLOBAL_SEED) -> int:
    """Seed every RNG (delegates to ml.config.seed_everything). Returns the seed."""
    return seed_everything(seed)


__all__ = [
    "dataset_hash",
    "feature_hash",
    "ScoreRecord",
    "ScoreLedger",
    "reconstruct_score",
    "RunRecord",
    "ReproTracker",
    "fixed_seed",
]
