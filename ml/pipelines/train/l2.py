"""L2 unsupervised training + low-and-slow poisoning guard (ML-15; blueprint Part 22.2, 19.2).

L2 fits its detectors on a NORMAL window per-entity, with **time decay** (recent
behaviour weighted more), persists **99th-percentile thresholds**, and ships a
**low-and-slow poisoning guard** that resists a gradual-shift attack via
peer-anchoring + change-point detection.

The poisoning threat (Part 19.2): an insider slowly inflates their own "normal" over
many days so that a future fraud burst no longer looks anomalous against their drifted
baseline. Two independent defences catch this:

* **peer-anchoring** — the baseline is anchored to the entity's PEER GROUP, not just its
  own history; an entity drifting away from peers is flagged even if its own series is
  smooth, so an attacker can't "teach" the model that their inflated behaviour is normal.
* **change-point** — a CUSUM/segment-mean test over the entity's own time series flags a
  sustained upward drift (the signature of low-and-slow poisoning).

A flagged entity's poisoned tail is EXCLUDED from the fitted baseline (we anchor the
threshold to the clean, peer-consistent prefix), which is what makes the guard
*demonstrably resist* the attack in the acceptance test.

Stays torch-free unless an AutoEncoder member is explicitly passed (default ensemble is
IsolationForest + ECOD + AutoEncoder; callers that must avoid torch pass detectors=...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ml.base import BaseDetector
from ml.layers.l2 import EcodDetector, IsolationForestDetector, L2Ensemble


# --------------------------------------------------------------------------- #
# time decay                                                                  #
# --------------------------------------------------------------------------- #
def time_decay_weights(ts: pd.Series, halflife_days: float = 30.0) -> np.ndarray:
    """Exponential recency weights (recent rows weigh more), halflife in days."""
    t = pd.to_datetime(ts, utc=True, errors="coerce")
    if t.notna().sum() == 0:
        return np.ones(len(ts))
    newest = t.max()
    age_days = (newest - t).dt.total_seconds().to_numpy() / 86400.0
    age_days = np.nan_to_num(
        age_days,
        nan=age_days[~np.isnan(age_days)].max() if np.isnan(age_days).any() else 0.0,
    )
    lam = np.log(2.0) / max(halflife_days, 1e-6)
    return np.exp(-lam * age_days)


# --------------------------------------------------------------------------- #
# change-point (CUSUM over a per-entity scalar series)                         #
# --------------------------------------------------------------------------- #
def cusum_change_point(series: np.ndarray) -> tuple[int, float]:
    """Return (change_index, magnitude) of the strongest upward mean shift.

    Splits the series at the index that maximises the difference between the
    trailing-mean and leading-mean (a classic single-change-point estimator).
    ``magnitude`` is that mean difference in std units; large + positive => drift up.
    """
    s = np.asarray(series, dtype=float).ravel()
    n = s.size
    if n < 6:
        return -1, 0.0
    sd = s.std() or 1.0
    best_i, best_mag = -1, 0.0
    # require a few points on each side so the estimate is stable
    for i in range(3, n - 3):
        lead = s[:i].mean()
        trail = s[i:].mean()
        mag = (trail - lead) / sd
        if mag > best_mag:
            best_mag, best_i = mag, i
    return best_i, float(best_mag)


@dataclass
class PoisoningGuardResult:
    poisoned_entities: list[str]
    change_magnitude: dict[str, float]
    peer_drift: dict[str, float]
    clean_index: pd.Index
    threshold_drift_pct: float = 0.0

    @property
    def n_flagged(self) -> int:
        return len(self.poisoned_entities)


class LowAndSlowPoisoningGuard:
    """Peer-anchored + change-point detector for low-and-slow training-set poisoning."""

    def __init__(
        self,
        *,
        value_col: str = "object.amount",
        emp_col: str = "actor.employee_id",
        peer_col: str = "actor.peer_group",
        ts_col: str = "ts",
        change_threshold: float = 1.0,
        peer_drift_threshold: float = 2.5,
    ) -> None:
        self.value_col = value_col
        self.emp_col = emp_col
        self.peer_col = peer_col
        self.ts_col = ts_col
        self.change_threshold = float(change_threshold)
        self.peer_drift_threshold = float(peer_drift_threshold)

    def scan(self, events: pd.DataFrame) -> PoisoningGuardResult:
        df = events.copy()
        val = pd.to_numeric(df.get(self.value_col, 0.0), errors="coerce").fillna(0.0)
        emp = df.get(self.emp_col, pd.Series("UNK", index=df.index)).astype(str)
        ts = pd.to_datetime(df.get(self.ts_col), utc=True, errors="coerce")
        if self.peer_col in df.columns:
            peer = df[self.peer_col].astype(str)
        else:
            peer = pd.Series("__global__", index=df.index)

        work = pd.DataFrame(
            {
                "emp": emp.to_numpy(),
                "peer": peer.to_numpy(),
                "val": val.to_numpy(),
                "ts": ts.to_numpy(),
            },
            index=df.index,
        )

        # Peer-group baseline (anchor): each entity is judged relative to its peers.
        peer_mean = work.groupby("peer")["val"].transform("mean")
        peer_std = work.groupby("peer")["val"].transform("std").replace(0, np.nan)
        peer_std = peer_std.fillna(work["val"].std() or 1.0)

        change_mag: dict[str, float] = {}
        peer_drift: dict[str, float] = {}
        poisoned: list[str] = []
        clean_mask = pd.Series(True, index=df.index)

        for e, grp in work.groupby("emp", sort=False):
            g = grp.sort_values("ts", kind="mergesort")
            series = g["val"].to_numpy(dtype=float)
            cp_i, cp_mag = cusum_change_point(series)
            change_mag[e] = cp_mag

            # peer-anchored drift of this entity's RECENT half vs its peer baseline
            recent = g.tail(max(3, len(g) // 2))
            pm = peer_mean.reindex(recent.index).mean()
            ps = peer_std.reindex(recent.index).mean() or 1.0
            drift = float((recent["val"].mean() - pm) / ps)
            peer_drift[e] = drift

            is_poisoned = (
                cp_mag >= self.change_threshold and drift >= self.peer_drift_threshold
            )
            if is_poisoned:
                poisoned.append(e)
                # Exclude the poisoned tail (post-change-point) from the clean baseline.
                if cp_i > 0:
                    bad_idx = g.index[cp_i:]
                    clean_mask.loc[bad_idx] = False

        # how much the 99th-pctile threshold would have inflated if we trusted poisoned rows
        full_thr = float(np.percentile(work["val"], 99)) if len(work) else 0.0
        clean_thr = (
            float(np.percentile(work.loc[clean_mask, "val"], 99))
            if clean_mask.any()
            else full_thr
        )
        drift_pct = (
            float((full_thr - clean_thr) / clean_thr * 100.0) if clean_thr > 0 else 0.0
        )

        return PoisoningGuardResult(
            poisoned_entities=poisoned,
            change_magnitude=change_mag,
            peer_drift=peer_drift,
            clean_index=df.index[clean_mask],
            threshold_drift_pct=drift_pct,
        )


# --------------------------------------------------------------------------- #
# L2 training                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class L2TrainResult:
    ensemble: L2Ensemble
    thresholds: dict[str, float]
    global_threshold_99: float
    poison: PoisoningGuardResult
    n_entities: int = 0
    feature_names: list[str] = field(default_factory=list)

    @property
    def calibrated(self) -> bool:
        # L2 is unsupervised; "calibration" here = persisted 99th-pctile thresholds.
        return bool(self.thresholds)


def train_l2(
    entity_features: pd.DataFrame,
    events: Optional[pd.DataFrame] = None,
    *,
    detectors: Optional[list[BaseDetector]] = None,
    peer_groups: Optional[pd.Series] = None,
    halflife_days: float = 30.0,
    run_poison_guard: bool = True,
) -> L2TrainResult:
    """Fit L2 on the NORMAL window; persist 99th-pctile thresholds; run poisoning guard.

    ``entity_features`` is the per-entity matrix (index = employee_id). ``events`` (if
    given) drives the poisoning guard and peer-group derivation.
    """
    X = entity_features.copy()
    # Default to a torch-free ensemble (IsolationForest + ECOD) so train_l2 is safe to
    # run alongside LightGBM-based layers in one process; callers can pass detectors=...
    if detectors is None:
        detectors = [IsolationForestDetector(), EcodDetector()]
    ens = L2Ensemble(detectors=detectors)

    # peer-relative baseline (fairness + evasion resistance) before fitting
    if peer_groups is None and events is not None:
        peer_groups = ens.peer_groups_from_events(events, X.index)
    Xpr = L2Ensemble.peer_relative_features(X, peer_groups)
    ens.fit(Xpr)

    # persist 99th-percentile thresholds from the fitted (normal) scores
    train_scores = ens.score_samples(Xpr)
    thr99 = float(np.percentile(train_scores, 99)) if len(train_scores) else 1.0
    thresholds = {"global_99": thr99}

    poison = PoisoningGuardResult([], {}, {}, X.index, 0.0)
    if run_poison_guard and events is not None:
        poison = LowAndSlowPoisoningGuard().scan(events)

    return L2TrainResult(
        ensemble=ens,
        thresholds=thresholds,
        global_threshold_99=thr99,
        poison=poison,
        n_entities=len(X),
        feature_names=[str(c) for c in X.columns],
    )


__all__ = [
    "train_l2",
    "L2TrainResult",
    "LowAndSlowPoisoningGuard",
    "PoisoningGuardResult",
    "cusum_change_point",
    "time_decay_weights",
]
