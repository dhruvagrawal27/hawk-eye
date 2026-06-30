"""Poisoning mitigations (ML-27; blueprint Part 19.2 — Poisoning, Part 22.2).

A patient insider poisons the *training data* "low and slow": they nudge their own
baseline upward a little each refresh so that, by the time they commit fraud, the model
has been taught the fraud is normal. The blueprint's mitigations, made concrete:

* :class:`TrainSetAnomalyCheck`     — anomaly-check incoming training rows BEFORE they
  enter the train set (drop/quarantine out-of-distribution rows).
* :func:`detect_low_and_slow_poisoning` — change-point detection + peer-anchored
  baselines: a gradual upward drift in ONE entity that its peer group does NOT share is a
  poisoning signature. This is the acceptance-test defense.
* :class:`LabelDistributionReview`  — flag abnormal shifts in the label mix (a poisoner
  flipping labels shows up as a distribution change).
* :class:`ImmutableLabelAudit`      — append-only hash chain over label events, so any
  retroactive label edit breaks the chain and is detectable.
* :class:`ProvenanceLedger`         — lineage: which dataset/source/actor produced each
  training row, so a poisoned batch can be traced and excised.

ALERT-ONLY: these raise reports/flags for a human; they never auto-delete production data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Train-set anomaly check                                                     #
# --------------------------------------------------------------------------- #
class TrainSetAnomalyCheck:
    """Quarantine training rows that are out-of-distribution vs the clean reference.

    Fit on a TRUSTED reference window; ``check`` returns a per-row mask of rows that are
    anomalous (robust per-feature z beyond ``z_thresh``) and should be quarantined, not
    silently trained on. Uses median/MAD so a few poisoned rows can't move the yardstick.
    """

    def __init__(self, z_thresh: float = 6.0) -> None:
        self.z_thresh = float(z_thresh)
        self._med: Optional[pd.Series] = None
        self._mad: Optional[pd.Series] = None
        self._cols: list[str] = []

    def fit(self, reference: pd.DataFrame) -> "TrainSetAnomalyCheck":
        ref = reference.select_dtypes(include=[np.number])
        self._cols = list(ref.columns)
        self._med = ref.median()
        # 1.4826 * MAD ~ robust sigma; floor to avoid divide-by-zero on constant columns.
        mad = (ref - self._med).abs().median() * 1.4826
        self._mad = mad.where(mad > 1e-9, 1.0)
        return self

    def robust_z(self, rows: pd.DataFrame) -> pd.DataFrame:
        if self._med is None or self._mad is None:
            raise RuntimeError("TrainSetAnomalyCheck must be fit first")
        r = (
            rows.reindex(columns=self._cols)
            .select_dtypes(include=[np.number])
            .astype(float)
        )
        return (r - self._med).abs() / self._mad

    def check(self, rows: pd.DataFrame) -> pd.Series:
        """Boolean Series (index = rows.index): True == anomalous == quarantine."""
        z = self.robust_z(rows)
        return (z > self.z_thresh).any(axis=1)

    def clean(self, rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Split into (accepted, quarantined) training rows."""
        bad = self.check(rows)
        return rows.loc[~bad], rows.loc[bad]


# --------------------------------------------------------------------------- #
# Change-point + peer-anchored low-and-slow detection (acceptance test)       #
# --------------------------------------------------------------------------- #
@dataclass
class PoisoningReport:
    """Outcome of a low-and-slow poisoning scan for one entity."""

    entity_id: str
    poisoning_suspected: bool
    change_point: Optional[int] = None
    drift_magnitude: float = 0.0
    peer_drift: float = 0.0
    peer_anchored_excess: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "poisoning_suspected": self.poisoning_suspected,
            "change_point": self.change_point,
            "drift_magnitude": round(float(self.drift_magnitude), 6),
            "peer_drift": round(float(self.peer_drift), 6),
            "peer_anchored_excess": round(float(self.peer_anchored_excess), 6),
            "detail": self.detail,
        }


def _change_point(series: np.ndarray, min_seg: int = 3) -> tuple[Optional[int], float]:
    """Single best mean-shift change point via max |left_mean - right_mean|.

    Returns (split_index, magnitude). Lightweight CUSUM-style detector (no extra deps);
    a low-and-slow poisoner's slow ramp still yields a detectable late-window mean shift.
    """
    s = np.asarray(series, dtype=float).ravel()
    n = s.size
    if n < 2 * min_seg:
        return None, 0.0
    best_i, best_mag = None, 0.0
    for i in range(min_seg, n - min_seg + 1):
        left, right = s[:i], s[i:]
        mag = abs(float(right.mean()) - float(left.mean()))
        if mag > best_mag:
            best_mag, best_i = mag, i
    return best_i, best_mag


def detect_low_and_slow_poisoning(
    entity_series: "pd.Series | np.ndarray | list",
    peer_series_by_entity: Optional[dict[str, Any]] = None,
    *,
    entity_id: str = "entity",
    min_seg: int = 3,
    drift_thresh: float = 0.0,
    peer_anchor_ratio: float = 2.0,
) -> PoisoningReport:
    """Detect a gradual upward baseline drift NOT shared by the entity's peers.

    The signature of low-and-slow poisoning: the entity's own metric ramps up over the
    training window (a change point with non-trivial magnitude) while the PEER group's
    median stays flat. ``peer_anchored_excess`` = entity drift minus peer drift; when the
    entity drifts at least ``peer_anchor_ratio`` x the peers (and the change point is real),
    poisoning is suspected.

    ``peer_series_by_entity`` maps peer entity_id -> their time series (same length); the
    peer drift is the MEDIAN of peer drifts, so a couple of co-conspirators can't hide it.
    """
    s = np.asarray(pd.Series(entity_series).astype(float).to_numpy()).ravel()
    cp, mag = _change_point(s, min_seg=min_seg)

    peer_drift = 0.0
    if peer_series_by_entity:
        drifts = []
        for _pid, pser in peer_series_by_entity.items():
            _, pmag = _change_point(
                np.asarray(pd.Series(pser).astype(float).to_numpy()), min_seg=min_seg
            )
            drifts.append(pmag)
        if drifts:
            peer_drift = float(np.median(drifts))

    excess = float(mag - peer_drift)
    # Suspected when: a real change point exists, the entity's drift clears the floor, and
    # it drifts materially more than its peers (peer-anchoring rules out a fleet-wide shift).
    suspected = bool(
        cp is not None
        and mag > drift_thresh
        and (
            peer_drift <= 1e-9
            and mag > drift_thresh
            or mag >= peer_anchor_ratio * max(peer_drift, 1e-9)
        )
        and excess > 0.0
    )
    detail = (
        f"entity drift {mag:.4f} at index {cp} vs peer-median drift {peer_drift:.4f} "
        f"(excess {excess:.4f})"
    )
    return PoisoningReport(
        entity_id=str(entity_id),
        poisoning_suspected=suspected,
        change_point=cp,
        drift_magnitude=mag,
        peer_drift=peer_drift,
        peer_anchored_excess=excess,
        detail=detail,
    )


# --------------------------------------------------------------------------- #
# Label-distribution review                                                   #
# --------------------------------------------------------------------------- #
class LabelDistributionReview:
    """Flag abnormal shifts in the label mix between a baseline and a new batch.

    A poisoner who flips labels (fraud->benign to teach the model to ignore them, or
    benign->fraud to bury real cases) perturbs the class distribution. Uses total
    variation distance plus a positive-rate delta; both trip a flag past their thresholds.
    """

    def __init__(self, tv_thresh: float = 0.15, pos_rate_thresh: float = 0.1) -> None:
        self.tv_thresh = float(tv_thresh)
        self.pos_rate_thresh = float(pos_rate_thresh)

    @staticmethod
    def _dist(y: Any) -> tuple[dict[Any, float], float]:
        s = pd.Series(y)
        vc = s.value_counts(normalize=True)
        pos_rate = float(s.astype(bool).mean()) if len(s) else 0.0
        return {k: float(v) for k, v in vc.items()}, pos_rate

    def review(self, baseline_labels: Any, new_labels: Any) -> dict[str, Any]:
        base_d, base_pos = self._dist(baseline_labels)
        new_d, new_pos = self._dist(new_labels)
        keys = set(base_d) | set(new_d)
        tv = 0.5 * sum(abs(base_d.get(k, 0.0) - new_d.get(k, 0.0)) for k in keys)
        pos_delta = abs(new_pos - base_pos)
        flagged = tv > self.tv_thresh or pos_delta > self.pos_rate_thresh
        return {
            "flagged": bool(flagged),
            "tv_distance": round(float(tv), 6),
            "baseline_pos_rate": round(base_pos, 6),
            "new_pos_rate": round(new_pos, 6),
            "pos_rate_delta": round(float(pos_delta), 6),
        }


# --------------------------------------------------------------------------- #
# Immutable label audit (append-only hash chain)                              #
# --------------------------------------------------------------------------- #
@dataclass
class _LabelLink:
    index: int
    payload: dict[str, Any]
    prev_hash: str
    this_hash: str


class ImmutableLabelAudit:
    """Append-only hash chain over label events (tamper-evident label store).

    Each appended label links to the previous entry's hash; any retroactive edit to a past
    label changes its hash and breaks every downstream link, so ``verify`` returns False.
    A poisoner who silently rewrites labels in the store is therefore detectable.
    """

    GENESIS = "0" * 64

    def __init__(self) -> None:
        self._chain: list[_LabelLink] = []

    @staticmethod
    def _hash(index: int, payload: dict[str, Any], prev_hash: str) -> str:
        blob = json.dumps(
            {"i": index, "p": payload, "prev": prev_hash}, sort_keys=True, default=str
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def append(self, event_id: str, is_fraud: bool, **meta: Any) -> str:
        prev = self._chain[-1].this_hash if self._chain else self.GENESIS
        idx = len(self._chain)
        payload = {"event_id": str(event_id), "is_fraud": bool(is_fraud), **meta}
        h = self._hash(idx, payload, prev)
        self._chain.append(
            _LabelLink(index=idx, payload=payload, prev_hash=prev, this_hash=h)
        )
        return h

    def head(self) -> str:
        return self._chain[-1].this_hash if self._chain else self.GENESIS

    def __len__(self) -> int:
        return len(self._chain)

    def verify(self) -> bool:
        """Re-derive every link; any tampered payload/link breaks the chain -> False."""
        prev = self.GENESIS
        for link in self._chain:
            if link.prev_hash != prev:
                return False
            if self._hash(link.index, link.payload, link.prev_hash) != link.this_hash:
                return False
            prev = link.this_hash
        return True

    def tamper(self, index: int, new_is_fraud: bool) -> None:
        """TEST/RED-TEAM ONLY: simulate a malicious in-place label edit (no re-hash)."""
        self._chain[index].payload["is_fraud"] = bool(new_is_fraud)


# --------------------------------------------------------------------------- #
# Provenance / lineage ledger                                                 #
# --------------------------------------------------------------------------- #
class ProvenanceLedger:
    """Track lineage of every training batch: source, actor, dataset hash, timestamp.

    When a poisoning report fires, lineage lets a human trace WHICH batch/source/actor
    introduced the bad rows and excise exactly that batch (Part 22.4 reproducibility).
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    @staticmethod
    def dataset_hash(df: pd.DataFrame) -> str:
        try:
            blob = pd.util.hash_pandas_object(df, index=True).values.tobytes()
        except Exception:
            blob = df.to_csv(index=True).encode()
        return hashlib.sha256(blob).hexdigest()

    def record(
        self,
        batch_id: str,
        df: pd.DataFrame,
        *,
        source: str,
        actor: str,
        ts: Optional[str] = None,
        **meta: Any,
    ) -> dict[str, Any]:
        rec = {
            "batch_id": str(batch_id),
            "n_rows": int(len(df)),
            "dataset_hash": self.dataset_hash(df),
            "source": source,
            "actor": actor,
            "ts": ts,
            **meta,
        }
        self._records.append(rec)
        return rec

    def lineage(self, batch_id: str) -> Optional[dict[str, Any]]:
        for rec in self._records:
            if rec["batch_id"] == str(batch_id):
                return rec
        return None

    def all(self) -> list[dict[str, Any]]:
        return list(self._records)
