"""Windowing helpers for L4 sequence models (ML-5).

Turns flattened L0 events into per-entity / per-session *event windows* — the unit
every L4 model consumes. A window is a fixed-length slice of an entity's ordered
event stream; the model decides whether that window is anomalous.

Two representations:
* ``build_windows`` -> dense numeric windows ``(n_windows, window, n_features)`` for
  the reconstruction / autoencoder family (PCA, IF, USAD, TranAD, AnomalyTransformer).
* ``build_verb_sequences`` -> per-session integer verb sequences for DeepLog
  (next-event language-model style).

All dtype checks use ``pd.api.types.*`` (pandas 2.3 / 3.0 safe). No heavy deps here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

EMP = "actor.employee_id"
TS = "ts"
VERB = "action.verb"
SESSION = "context.session_id"
AMOUNT = "object.amount"
OFF_HOURS = "context.is_off_hours"


def _col(df: pd.DataFrame, name: str, default=0.0) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index, name=name)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def _bool_int(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.astype(int)
    return _num(s).astype(int).clip(0, 1)


# Verbs that carry the most sequence signal (used for the per-step one-hot feature).
SEQ_VERBS = (
    "login",
    "approve_payment",
    "create_beneficiary",
    "export",
    "grant_entitlement",
    "db_select",
    "db_write",
    "post_journal",
)


def step_features(df: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Per-event numeric feature matrix (one row per event), index-aligned to ``df``.

    Compact, leakage-safe step features: log-amount, off-hours flag, inter-arrival
    gap is added by the windower, plus a one-hot over the high-signal verbs.
    """
    amt = _num(_col(df, AMOUNT, 0.0)).astype(float)
    log_amt = np.log1p(np.clip(amt.to_numpy(), 0, None))
    off = _bool_int(_col(df, OFF_HOURS, 0)).to_numpy(dtype=float)

    verbs = _col(df, VERB, "").astype(str)
    onehot = np.zeros((len(df), len(SEQ_VERBS)), dtype=float)
    for j, v in enumerate(SEQ_VERBS):
        onehot[:, j] = (verbs == v).to_numpy(dtype=float)

    feats = np.column_stack([log_amt, off, onehot])
    names = ["log_amount", "off_hours", *[f"verb={v}" for v in SEQ_VERBS]]
    return feats.astype(np.float32), names


def _entity_order(df: pd.DataFrame) -> pd.DataFrame:
    ts = pd.to_datetime(_col(df, TS, None), utc=True, errors="coerce")
    out = df.copy()
    out["__ts__"] = ts
    out["__entity__"] = _col(df, EMP, "UNK").astype(str)
    return out.sort_values(["__entity__", "__ts__"], kind="mergesort")


@dataclass
class WindowSet:
    """A set of windows plus the metadata needed to evaluate them honestly."""

    X: np.ndarray  # (n_windows, window, n_features)
    entity: np.ndarray  # (n_windows,) entity id per window
    end_ts: np.ndarray  # (n_windows,) datetime64 of the window's last event
    y: np.ndarray  # (n_windows,) 1 if any event in the window is fraud
    feature_names: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return int(self.X.shape[0])

    @property
    def flat(self) -> np.ndarray:
        """Windows flattened to 2-D ``(n_windows, window*n_features)`` for PCA / IF."""
        n = self.X.shape[0]
        return self.X.reshape(n, -1) if n else self.X.reshape(0, 0)


def build_windows(
    events: pd.DataFrame,
    labels: Optional[pd.Series] = None,
    *,
    window: int = 20,
    stride: int = 1,
    min_events: int = 1,
) -> WindowSet:
    """Build per-entity sliding event windows of length ``window``.

    ``labels`` (optional) is a 0/1 Series aligned to ``events.index``; a window's
    label is the max over its events (1 if it contains any fraud event). Entities
    with fewer than ``window`` events are right-padded so they still yield one
    window (so tiny synthetic fixtures always produce data).
    """
    window = max(2, int(window))
    stride = max(1, int(stride))
    feats, names = step_features(events)

    if labels is not None:
        y_evt = np.asarray(labels.reindex(events.index).fillna(0)).astype(int).ravel()
    else:
        y_evt = np.zeros(len(events), dtype=int)

    ordered = _entity_order(events)
    pos = {idx: i for i, idx in enumerate(events.index)}

    Xs: list[np.ndarray] = []
    ents: list[str] = []
    ends: list[np.datetime64] = []
    ys: list[int] = []

    for ent, grp in ordered.groupby("__entity__", sort=False):
        rows = [pos[i] for i in grp.index]
        if len(rows) < min_events:
            continue
        ts_vals = grp["__ts__"].to_numpy()
        n = len(rows)
        if n < window:
            # right-pad by repeating the last event so short entities still score.
            starts = [0]
        else:
            starts = list(range(0, n - window + 1, stride))
        for s in starts:
            sel = rows[s : s + window]
            block = feats[sel]
            if block.shape[0] < window:
                pad = np.repeat(block[-1:], window - block.shape[0], axis=0)
                block = np.vstack([block, pad])
            Xs.append(block)
            ents.append(ent)
            ends.append(ts_vals[min(s + window, n) - 1])
            ys.append(int(y_evt[sel].max()) if len(sel) else 0)

    if not Xs:
        X = np.zeros((0, window, feats.shape[1]), dtype=np.float32)
        return WindowSet(X, np.array([]), np.array([], dtype="datetime64[ns]"),
                         np.array([], dtype=int), names)

    X = np.stack(Xs).astype(np.float32)
    return WindowSet(
        X=X,
        entity=np.asarray(ents),
        end_ts=np.asarray(ends, dtype="datetime64[ns]"),
        y=np.asarray(ys, dtype=int),
        feature_names=names,
    )


def build_verb_sequences(
    events: pd.DataFrame,
    labels: Optional[pd.Series] = None,
    *,
    by: str = "session",
) -> tuple[list[list[int]], list[int], dict[str, int]]:
    """Per-session (or per-entity) integer verb sequences for DeepLog.

    Returns ``(sequences, seq_labels, vocab)`` where ``vocab`` maps verb->id (id 0 is
    reserved for the padding / unknown token). A sequence's label is 1 if any event
    in it is fraud.
    """
    verbs = _col(events, VERB, "").astype(str)
    vocab: dict[str, int] = {"<pad>": 0}
    for v in sorted(verbs.unique()):
        if v not in vocab:
            vocab[v] = len(vocab)

    if labels is not None:
        y_evt = pd.Series(np.asarray(labels.reindex(events.index).fillna(0)).astype(int),
                          index=events.index)
    else:
        y_evt = pd.Series(0, index=events.index)

    key_col = SESSION if (by == "session" and SESSION in events.columns) else EMP
    keys = _col(events, key_col, "UNK").astype(str)
    ts = pd.to_datetime(_col(events, TS, None), utc=True, errors="coerce")

    tmp = pd.DataFrame({"key": keys.to_numpy(), "ts": ts.to_numpy(),
                        "verb": verbs.to_numpy(), "y": y_evt.to_numpy()},
                       index=events.index).sort_values(["key", "ts"], kind="mergesort")

    seqs: list[list[int]] = []
    seq_y: list[int] = []
    for _, grp in tmp.groupby("key", sort=False):
        seqs.append([vocab.get(v, 0) for v in grp["verb"]])
        seq_y.append(int(grp["y"].max()))
    return seqs, seq_y, vocab
