"""Layer-parameterized training DAG (ML-14; blueprint Part 22.1).

The training DAG, as plain-Python orchestration with ordered steps:

    pull -> build_features -> train -> validate -> calibrate -> register(MLflow)
         -> optional shadow-deploy

``TrainingDAG`` runs end-to-end on a ``DataSimFeatureSource`` for ANY layer param
(L2/L3/L4/L5/L6) and produces a REGISTERED run (MLflow when present, else a local JSON
run record via :class:`ml.pipelines.repro.ReproTracker`). Each step is a method, ordered
in :attr:`STEPS`, and :meth:`run` executes them in order, accumulating a context dict.

An Airflow-DAG factory (:func:`make_airflow_dag`) is provided too, guarded by
``optional_import('airflow')`` — it is SCAFFOLD when airflow is absent (logged + returns
None) so the module always imports.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml._optional import optional_import
from ml.adapters import DataSimFeatureSource, FeatureSource
from ml.pipelines import repro
from ml.pipelines.train import LAYERS, get_trainer

log = logging.getLogger("ml.pipelines.train_dag")

SUPERVISED_LAYERS = ("L3", "L5", "L6")

# Layers whose trainers may load torch (deep / GNN). The rest are tree/sklearn only.
# We seed WITHOUT touching torch for tree layers, because seeding torch would co-load it
# with LightGBM in one process and trigger the macOS dual-libomp segfault.
_TORCH_FREE_SEED_LAYERS = ("L2", "L3", "L5", "L6")


def _seed_for_layer(layer: str, seed: int) -> None:
    """Reproducible seeding. For tree layers, seed numpy/random WITHOUT importing torch."""
    import random

    import os as _os

    _os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    if layer not in _TORCH_FREE_SEED_LAYERS:
        from ml.config.seeds import seed_everything

        seed_everything(seed)


@dataclass
class DAGRunResult:
    layer: str
    run: repro.RunRecord
    metrics: dict[str, float]
    calibrated: bool
    artifact: Any = None
    shadow_deployed: bool = False
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer": self.layer,
            "run_id": self.run.run_id,
            "model_version": self.run.model_version,
            "metrics": self.metrics,
            "calibrated": self.calibrated,
            "registered_backend": self.run.backend,
            "shadow_deployed": self.shadow_deployed,
        }


class TrainingDAG:
    """Ordered pull -> features -> train -> validate -> calibrate -> register -> shadow."""

    STEPS = (
        "pull",
        "build_features",
        "train",
        "validate",
        "calibrate",
        "register",
        "shadow_deploy",
    )

    def __init__(
        self,
        layer: str,
        *,
        source: Optional[FeatureSource] = None,
        tracker: Optional[repro.ReproTracker] = None,
        shadow: bool = False,
        seed: int = 1405,
        trainer_kwargs: Optional[dict[str, Any]] = None,
    ) -> None:
        layer = layer.upper()
        if layer not in LAYERS:
            raise ValueError(f"unknown layer {layer!r}; expected one of {LAYERS}")
        self.layer = layer
        self.source = source or DataSimFeatureSource()
        self.tracker = tracker or repro.ReproTracker()
        self.shadow = shadow
        self.seed = seed
        self.trainer_kwargs = dict(trainer_kwargs or {})
        self._ctx: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # steps                                                              #
    # ------------------------------------------------------------------ #
    def pull(self, ctx: dict) -> None:
        _seed_for_layer(self.layer, self.seed)
        ctx["events"] = self.source.events()
        ctx["labels"] = self.source.labels()
        ctx["dataset_hash"] = repro.dataset_hash(ctx["events"], ctx["labels"])

    def build_features(self, ctx: dict) -> None:
        layer = self.layer
        events = ctx["events"]
        if layer == "L3":
            X, y = self.source.supervised_xy()
            ts = (
                events.set_index("event_id")["ts"].reindex(X.index)
                if "event_id" in events.columns
                else None
            )
            ctx["X"], ctx["y"], ctx["ts"] = X, y, ts
            ctx["feature_names"] = [str(c) for c in X.columns]
        elif layer in ("L2", "L5"):
            ctx["X"] = self.source.entity_features()
            ctx["y"] = self.source.entity_labels()
            ctx["feature_names"] = [str(c) for c in ctx["X"].columns]
        elif layer == "L4":
            X = self.source.event_features()
            ctx["X"] = X
            ctx["y_event"] = self.source.event_labels()
            ctx["feature_names"] = [str(c) for c in X.columns]
        elif layer == "L6":
            ctx["layer_scores"], ctx["y"] = self._build_l6_inputs()
            ctx["feature_names"] = [str(c) for c in ctx["layer_scores"].columns]

    def train(self, ctx: dict) -> None:
        trainer = get_trainer(self.layer)
        kw = self.trainer_kwargs
        if self.layer == "L3":
            ctx["result"] = trainer(ctx["X"], ctx["y"], ctx.get("ts"), **kw)
        elif self.layer == "L2":
            ctx["result"] = trainer(ctx["X"], events=ctx["events"], **kw)
        elif self.layer == "L5":
            ctx["result"] = trainer(ctx["X"], ctx["y"], ctx["events"], **kw)
        elif self.layer == "L4":
            ctx["result"] = trainer(ctx["events"], labels=ctx["y_event"], **kw)
        elif self.layer == "L6":
            ctx["result"] = trainer(ctx["layer_scores"], ctx["y"], **kw)

    def validate(self, ctx: dict) -> None:
        res = ctx["result"]
        metrics = dict(getattr(res, "metrics", {}) or {})
        # Honest-eval sanity: supervised layers must beat a random baseline on AUPRC.
        ap = metrics.get("auprc")
        if self.layer in SUPERVISED_LAYERS and ap is not None and np.isfinite(ap):
            base_rate = float(np.mean(ctx.get("y", []))) if "y" in ctx else 0.0
            metrics["beats_random"] = float(ap >= base_rate)
        ctx["metrics"] = metrics

    def calibrate(self, ctx: dict) -> None:
        # Calibration is performed INSIDE each trainer (isotonic for supervised, 99th
        # -pctile thresholds for L2). Here we just assert the artifact reports calibrated.
        ctx["calibrated"] = bool(getattr(ctx["result"], "calibrated", False))

    def register(self, ctx: dict) -> None:
        res = ctx["result"]
        artifact = _artifact_of(res)
        model_version = getattr(
            artifact, "model_version", f"{self.layer.lower()}@0.1.0"
        )
        run = repro.RunRecord(
            run_id=f"{self.layer.lower()}-{int(time.time()*1000)}",
            layer=self.layer,
            model_version=str(model_version),
            params={"seed": self.seed, **self.trainer_kwargs},
            metrics={
                k: float(v)
                for k, v in ctx["metrics"].items()
                if isinstance(v, (int, float)) and np.isfinite(v)
            },
            dataset_hash=ctx.get("dataset_hash"),
            feature_hash=repro.feature_hash(ctx.get("feature_names", [])),
            feature_names=ctx.get("feature_names", []),
            seed=self.seed,
            calibrated=ctx["calibrated"],
        )
        ctx["run"] = self.tracker.log_run(run)
        ctx["artifact"] = artifact

    def shadow_deploy(self, ctx: dict) -> None:
        if not self.shadow:
            ctx["shadow_deployed"] = False
            return
        # Shadow = register the challenger so it can score live traffic WITHOUT emitting
        # alerts (handled by ml.pipelines.inference.shadow). Here we just flag it.
        ctx["shadow_deployed"] = True
        log.info(
            "shadow-deployed %s challenger %s", self.layer, ctx["run"].model_version
        )

    # ------------------------------------------------------------------ #
    def run(self) -> DAGRunResult:
        ctx: dict[str, Any] = {}
        for step in self.STEPS:
            getattr(self, step)(ctx)
        self._ctx = ctx
        return DAGRunResult(
            layer=self.layer,
            run=ctx["run"],
            metrics=ctx["metrics"],
            calibrated=ctx["calibrated"],
            artifact=ctx["artifact"],
            shadow_deployed=ctx.get("shadow_deployed", False),
            context=ctx,
        )

    # ------------------------------------------------------------------ #
    def _build_l6_inputs(self) -> tuple[pd.DataFrame, np.ndarray]:
        """Assemble a per-entity per-layer score matrix from L2 + L3 for the L6 meta-train.

        Uses the real L2 ensemble (torch-free) and the L3 LightGBM scorer to produce
        L2_unsupervised / L3_gbdt columns over the shared entity index, plus a cheap rule
        flag — enough to train + calibrate the stacked meta honestly.
        """
        from ml.layers.l2 import EcodDetector, IsolationForestDetector, L2Ensemble
        from ml.layers.l3 import LightGBMScorer

        ef = self.source.entity_features()
        ey = self.source.entity_labels()
        ens = L2Ensemble(detectors=[IsolationForestDetector(), EcodDetector()])
        Xpr = L2Ensemble.peer_relative_features(ef)
        ens.fit(Xpr)
        l2 = ens.score_samples(Xpr)

        # L3 per-event -> aggregate to per-entity max P(fraud). Shuffle so the scorer's
        # internal early-stopping tail-split sees positives in BOTH portions (the raw
        # DataSim order clusters all fraud, which would starve one side of a class).
        Xe, ye = self.source.supervised_xy()
        ye = pd.Series(np.asarray(ye).astype(int).ravel(), index=Xe.index)
        rng = np.random.default_rng(self.seed)
        perm = rng.permutation(len(Xe))
        Xe_s, ye_s = Xe.iloc[perm], ye.iloc[perm]
        l3_scorer = LightGBMScorer(n_estimators=200, use_scale_pos_weight=True)
        l3_scorer.fit(Xe_s, ye_s)
        ev = self.source.events()
        emp = (
            ev.set_index("event_id")["actor.employee_id"]
            if "event_id" in ev.columns
            else None
        )
        p_event = pd.Series(l3_scorer.predict_proba(Xe), index=Xe.index)
        if emp is not None:
            emp = emp.reindex(Xe.index)
            l3_entity = p_event.groupby(emp.to_numpy()).max()
            l3 = l3_entity.reindex(ef.index).fillna(0.0).to_numpy()
        else:
            l3 = np.zeros(len(ef))

        rule = (
            (ef.get("n_export", pd.Series(0.0, index=ef.index)).to_numpy() > 0).astype(
                float
            )
            if "n_export" in ef.columns
            else np.zeros(len(ef))
        )

        scores = pd.DataFrame(
            {
                "L1_rule": rule,
                "L2_unsupervised": l2,
                "L3_gbdt": l3,
            },
            index=ef.index,
        )
        return scores, np.asarray(ey).astype(int).ravel()


# --------------------------------------------------------------------------- #
# Airflow factory (SCAFFOLD when airflow absent)                              #
# --------------------------------------------------------------------------- #
def make_airflow_dag(
    layer: str,
    *,
    dag_id: Optional[str] = None,
    schedule: str = "@daily",
    shadow: bool = False,
):
    """Build an Airflow DAG mirroring :attr:`TrainingDAG.STEPS` (one task per step).

    Guarded by ``optional_import('airflow')``. When airflow is absent this is SCAFFOLD:
    it logs that fact and returns ``None`` (the plain-Python ``TrainingDAG`` is the real,
    always-runnable orchestration; the Airflow wrapper is for production scheduling).
    """
    airflow = optional_import("airflow")
    if airflow is None:
        # SCAFFOLD: airflow not installed on the ML venv.
        log.info(
            "airflow not installed; make_airflow_dag is SCAFFOLD (use TrainingDAG directly)"
        )
        return None

    from airflow import DAG  # pragma: no cover - airflow not on reference venv
    from airflow.operators.python import PythonOperator  # pragma: no cover

    dag_id = dag_id or f"hawkeye_train_{layer.lower()}"

    def _make_task(step: str):  # pragma: no cover
        def _run(**_kw):
            dag = TrainingDAG(layer, shadow=shadow)
            # Each Airflow task runs one step against a fresh ctx in XCom in real use;
            # for the scaffold we run the whole DAG on the final step.
            if step == TrainingDAG.STEPS[-1]:
                return dag.run().to_dict()
            return {"step": step}

        return _run

    with DAG(
        dag_id=dag_id, schedule=schedule, start_date=None, catchup=False
    ) as dag:  # pragma: no cover
        prev = None
        for step in TrainingDAG.STEPS:
            task = PythonOperator(task_id=step, python_callable=_make_task(step))
            if prev is not None:
                prev >> task
            prev = task
    return dag  # pragma: no cover


def run_training(layer: str, **kwargs) -> DAGRunResult:
    """Convenience: build + run a TrainingDAG for ``layer`` end-to-end."""
    return TrainingDAG(layer, **kwargs).run()


__all__ = [
    "TrainingDAG",
    "DAGRunResult",
    "make_airflow_dag",
    "run_training",
    "SUPERVISED_LAYERS",
]


def _artifact_of(res: Any) -> Any:
    """Pull the registrable model artifact out of a per-layer train result."""
    for attr in ("scorer", "fusion", "ensemble"):
        a = getattr(res, attr, None)
        if a is not None:
            return a
    return res
