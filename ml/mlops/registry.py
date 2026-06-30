"""Model registry conventions (ML-20; blueprint Part 18, 22.4, 27).

Every registered model carries the lineage that makes its scores auditable and a
deployment defensible to model-risk reviewers:

* the **training-data hash** (so the exact dataset can be identified),
* the **feature schema hash + names** (the train/serve contract),
* the **metrics** it was validated on (AUPRC / Rec@K / ...),
* the **approving reviewer** (independent validation sign-off — Part 27),
* a **champion / challenger** stage so a challenger can be registered, shadow-scored,
  and only promoted to champion after it beats the incumbent.

Uses **MLflow** (``mlflow.register_model`` / model-version stages) when present
(:func:`ml._optional.optional_import`), else a self-contained **local JSON registry**
that mirrors the same conventions and always works. Either way the artefact bytes are
written into DATABASE's ``models`` bucket layout via :class:`ml.adapters.ModelStore`.

Nothing here imports a heavy model library, so it loads in any process (torch OR
LightGBM) without the macOS dual-libomp hazard.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ml._optional import HAS_MLFLOW, optional_import
from ml.adapters.store import DEFAULT_ARTIFACT_ROOT, ModelStore
from ml.config.seeds import GLOBAL_SEED

# Champion/challenger registry stages (mirror MLflow model-version stages).
STAGE_CHALLENGER = "challenger"
STAGE_CHAMPION = "champion"
STAGE_ARCHIVED = "archived"
STAGES = (STAGE_CHALLENGER, STAGE_CHAMPION, STAGE_ARCHIVED)

DEFAULT_REGISTRY_ROOT = os.path.join(DEFAULT_ARTIFACT_ROOT, "registry")


def model_signature(feature_names: Any, *, model_version: str = "") -> str:
    """A stable signature over the ordered feature schema (+ optional version).

    Loading a model whose live feature schema does not hash to its registered signature
    is rejected (ML-21 signature verification): it means the serving feature contract
    drifted from what was trained.
    """
    names = "|".join(str(c) for c in feature_names)
    return hashlib.sha256(f"{names}::{model_version}".encode()).hexdigest()[:16]


@dataclass
class ModelRecord:
    """A registered model version + its full lineage (the ML-20 acceptance contract)."""

    name: str
    version: str
    layer: str
    stage: str = STAGE_CHALLENGER
    training_data_hash: Optional[str] = None
    feature_hash: Optional[str] = None
    feature_names: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    approving_reviewer: Optional[str] = None
    signature: Optional[str] = None
    seed: int = GLOBAL_SEED
    backend: str = "local"
    artifact_path: Optional[str] = None
    parent_version: Optional[str] = (
        None  # the champion a challenger was registered against
    )
    ts: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def model_version(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def is_complete(self) -> bool:
        """Every registered model MUST carry data-hash + features + metrics + reviewer."""
        return bool(
            self.training_data_hash
            and self.feature_names
            and self.metrics
            and self.approving_reviewer
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ts"] = self.ts or time.time()
        d["model_version"] = self.model_version
        d["is_complete"] = self.is_complete
        return d


class ModelRegistry:
    """Champion/challenger registry: MLflow when present, else a local JSON store.

    The local store is an append-only JSONL log of ``ModelRecord`` snapshots plus a small
    ``stages.json`` index mapping ``name -> {champion, challengers[]}``. Both backends keep
    a local copy so the registry is always queryable offline (mirrors ``ReproTracker``).
    """

    def __init__(
        self,
        *,
        root: Optional[str] = None,
        model_store: Optional[ModelStore] = None,
        use_mlflow: Optional[bool] = None,
    ) -> None:
        self.root = root or DEFAULT_REGISTRY_ROOT
        os.makedirs(self.root, exist_ok=True)
        self.model_store = model_store or ModelStore(root=os.path.dirname(self.root))
        self.use_mlflow = (
            HAS_MLFLOW if use_mlflow is None else (use_mlflow and HAS_MLFLOW)
        )
        self.backend = "mlflow" if self.use_mlflow else "local"
        self._log_path = os.path.join(self.root, "models.jsonl")
        self._stage_path = os.path.join(self.root, "stages.json")

    # --- registration --------------------------------------------------- #
    def register(
        self,
        *,
        name: str,
        version: str,
        layer: str,
        training_data_hash: Optional[str],
        feature_names: Any,
        metrics: dict[str, float],
        approving_reviewer: Optional[str],
        stage: str = STAGE_CHALLENGER,
        model: Any = None,
        parent_version: Optional[str] = None,
        require_complete: bool = True,
        extra: Optional[dict[str, Any]] = None,
    ) -> ModelRecord:
        """Register a model version with its full lineage.

        ``require_complete`` enforces the ML-20 acceptance rule: a registered model MUST
        carry data-hash + features + metrics + reviewer. Pass ``require_complete=False``
        only for an explicitly-incomplete draft (raises otherwise).
        """
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}, got {stage!r}")
        fnames = [str(c) for c in feature_names]
        rec = ModelRecord(
            name=name,
            version=version,
            layer=layer,
            stage=stage,
            training_data_hash=training_data_hash,
            feature_hash=hashlib.sha256("|".join(fnames).encode()).hexdigest()[:16],
            feature_names=fnames,
            metrics={k: float(v) for k, v in (metrics or {}).items()},
            approving_reviewer=approving_reviewer,
            signature=model_signature(fnames, model_version=f"{name}@{version}"),
            backend=self.backend,
            parent_version=parent_version,
            extra=extra or {},
        )
        if require_complete and not rec.is_complete:
            missing = [
                k
                for k, ok in (
                    ("training_data_hash", training_data_hash),
                    ("feature_names", fnames),
                    ("metrics", metrics),
                    ("approving_reviewer", approving_reviewer),
                )
                if not ok
            ]
            raise ValueError(
                f"incomplete registration for {name}@{version}: missing {missing}. "
                "Every registered model must carry data-hash/features/metrics/reviewer."
            )

        if model is not None:
            try:
                rec.artifact_path = self.model_store.save_model(
                    model, meta=rec.to_dict()
                )
            except Exception:
                rec.artifact_path = None

        self._append(rec)
        self._index_stage(rec)
        if self.use_mlflow:
            try:
                self._register_mlflow(rec)
            except Exception:
                rec.backend = "local"
        return rec

    # --- champion / challenger layout ----------------------------------- #
    def _load_stages(self) -> dict[str, dict[str, Any]]:
        if os.path.isfile(self._stage_path):
            with open(self._stage_path) as fh:
                return json.load(fh)
        return {}

    def _save_stages(self, idx: dict[str, dict[str, Any]]) -> None:
        with open(self._stage_path, "w") as fh:
            json.dump(idx, fh, indent=2, default=str)

    def _index_stage(self, rec: ModelRecord) -> None:
        idx = self._load_stages()
        entry = idx.setdefault(rec.name, {"champion": None, "challengers": []})
        if rec.stage == STAGE_CHAMPION:
            entry["champion"] = rec.version
            entry["challengers"] = [v for v in entry["challengers"] if v != rec.version]
        elif rec.stage == STAGE_CHALLENGER:
            if rec.version not in entry["challengers"]:
                entry["challengers"].append(rec.version)
        elif rec.stage == STAGE_ARCHIVED:
            entry["challengers"] = [v for v in entry["challengers"] if v != rec.version]
            if entry.get("champion") == rec.version:
                entry["champion"] = None
        self._save_stages(idx)

    def promote(
        self, name: str, version: str, *, reviewer: Optional[str] = None
    ) -> ModelRecord:
        """Promote a registered challenger version to champion (archives the old champion)."""
        idx = self._load_stages()
        entry = idx.get(name)
        if not entry:
            raise KeyError(f"no registered model named {name!r}")
        prev = entry.get("champion")
        if prev and prev != version:
            self._set_stage(name, prev, STAGE_ARCHIVED)
        rec = self._latest(name, version)
        if rec is None:
            raise KeyError(f"{name}@{version} is not registered")
        rec.stage = STAGE_CHAMPION
        if reviewer:
            rec.approving_reviewer = reviewer
        self._append(rec)
        self._index_stage(rec)
        return rec

    def _set_stage(self, name: str, version: str, stage: str) -> None:
        rec = self._latest(name, version)
        if rec is None:
            return
        rec.stage = stage
        self._append(rec)
        self._index_stage(rec)

    def champion(self, name: str) -> Optional[ModelRecord]:
        v = self._load_stages().get(name, {}).get("champion")
        return self._latest(name, v) if v else None

    def challengers(self, name: str) -> list[ModelRecord]:
        vs = self._load_stages().get(name, {}).get("challengers", [])
        return [r for r in (self._latest(name, v) for v in vs) if r is not None]

    # --- queries -------------------------------------------------------- #
    def _append(self, rec: ModelRecord) -> None:
        if not rec.ts:
            rec.ts = time.time()
        with open(self._log_path, "a") as fh:
            fh.write(json.dumps(rec.to_dict()) + "\n")

    def records(self) -> list[ModelRecord]:
        if not os.path.isfile(self._log_path):
            return []
        out: list[ModelRecord] = []
        with open(self._log_path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                d.pop("model_version", None)
                d.pop("is_complete", None)
                out.append(ModelRecord(**d))
        return out

    def _latest(self, name: str, version: Optional[str]) -> Optional[ModelRecord]:
        """Most recent snapshot for a name@version (records are append-only)."""
        if version is None:
            return None
        match = [r for r in self.records() if r.name == name and r.version == version]
        return match[-1] if match else None

    def get(self, name: str, version: str) -> Optional[ModelRecord]:
        return self._latest(name, version)

    def _register_mlflow(
        self, rec: ModelRecord
    ) -> None:  # pragma: no cover - mlflow optional path
        mlflow = optional_import("mlflow")
        if mlflow is None:
            return
        tracking_dir = os.path.join(self.root, "mlruns")
        os.makedirs(tracking_dir, exist_ok=True)
        mlflow.set_tracking_uri(f"file:{tracking_dir}")
        mlflow.set_experiment("hawkeye-registry")
        with mlflow.start_run(run_name=f"{rec.name}-{rec.version}"):
            mlflow.set_tags(
                {
                    "name": rec.name,
                    "version": rec.version,
                    "layer": rec.layer,
                    "stage": rec.stage,
                    "training_data_hash": rec.training_data_hash or "",
                    "feature_hash": rec.feature_hash or "",
                    "approving_reviewer": rec.approving_reviewer or "",
                    "signature": rec.signature or "",
                }
            )
            mlflow.log_metrics(
                {k: float(v) for k, v in rec.metrics.items() if v is not None}
            )


__all__ = [
    "STAGE_CHALLENGER",
    "STAGE_CHAMPION",
    "STAGE_ARCHIVED",
    "STAGES",
    "ModelRecord",
    "ModelRegistry",
    "model_signature",
]
