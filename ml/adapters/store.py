"""Model store + label store adapters (ML-1; prompt §3 stubbing).

# STUB: DATABASE — local filesystem stand-ins for the object-store ``models`` bucket
# and the EDD labeled-disposition store until DATABASE provides MinIO/Postgres/ClickHouse.
# Swap the backends without changing callers.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Optional

import pandas as pd

from ml.base.interfaces import BaseModel

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ARTIFACT_ROOT = os.path.join(REPO_ROOT, "ml", "_artifacts")


class ModelStore:
    """Filesystem model store mirroring DATABASE's ``models`` bucket layout.

    Layout: ``<root>/models/<name>/<version>/model.joblib`` (+ ``meta.json``).
    """

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = os.path.join(root or DEFAULT_ARTIFACT_ROOT, "models")
        os.makedirs(self.root, exist_ok=True)

    def _dir(self, name: str, version: str) -> str:
        d = os.path.join(self.root, name, version)
        os.makedirs(d, exist_ok=True)
        return d

    def save_model(self, model: BaseModel, *, meta: Optional[dict] = None) -> str:
        d = self._dir(model.name, model.version)
        path = os.path.join(d, "model.joblib")
        model.save(path)
        with open(os.path.join(d, "meta.json"), "w") as fh:
            json.dump({"name": model.name, "version": model.version, "layer": model.layer,
                       "saved_ts": time.time(), **(meta or {})}, fh, indent=2, default=str)
        return path

    def load_model(self, name: str, version: str) -> BaseModel:
        return BaseModel.load(os.path.join(self.root, name, version, "model.joblib"))

    def list_models(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not os.path.isdir(self.root):
            return out
        for name in sorted(os.listdir(self.root)):
            ndir = os.path.join(self.root, name)
            if not os.path.isdir(ndir):
                continue
            for version in sorted(os.listdir(ndir)):
                meta_path = os.path.join(ndir, version, "meta.json")
                if os.path.isfile(meta_path):
                    with open(meta_path) as fh:
                        out.append(json.load(fh))
        return out


@dataclass
class Disposition:
    """An EDD investigator disposition -> label (BACKEND.md §5)."""

    alert_id: str
    entity_id: str
    outcome: str  # "fraud" | "false_positive" | "inconclusive"
    event_ids: list[str]
    notes: str = ""
    ts: float = 0.0


class LabelStore:
    """JSON-backed labeled-disposition store for the EDD feedback loop (ML-16).

    # STUB: DATABASE/BACKEND own the real disposition write path
    # (``POST /alerts/{id}/disposition``); this is a local stand-in.
    """

    OUTCOMES = ("fraud", "false_positive", "inconclusive")

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or os.path.join(DEFAULT_ARTIFACT_ROOT, "labels", "dispositions.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def add_disposition(self, d: Disposition) -> None:
        if d.outcome not in self.OUTCOMES:
            raise ValueError(f"outcome must be one of {self.OUTCOMES}, got {d.outcome!r}")
        if not d.ts:
            d.ts = time.time()
        with open(self.path, "a") as fh:
            fh.write(json.dumps(asdict(d)) + "\n")

    def dispositions(self) -> list[Disposition]:
        if not os.path.isfile(self.path):
            return []
        out = []
        with open(self.path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(Disposition(**json.loads(line)))
        return out

    def labels(self) -> pd.DataFrame:
        """Event-level labels derived from dispositions (outcome 'fraud' -> is_fraud=1)."""
        rows: list[dict] = []
        for d in self.dispositions():
            is_fraud = d.outcome == "fraud"
            for eid in d.event_ids:
                rows.append({"event_id": eid, "is_fraud": is_fraud, "actor_id": d.entity_id,
                             "label_source": "edd", "confidence": 1.0 if d.outcome != "inconclusive" else 0.5})
        return pd.DataFrame(rows, columns=["event_id", "is_fraud", "actor_id", "label_source", "confidence"])
