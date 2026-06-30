"""Evasion mitigations (ML-27; blueprint Part 19.2 — Evasion).

An insider who reverse-engineers ONE detector can shape inputs to slip under it. The
blueprint's four mitigations, made concrete here:

1. **Peer-relative baselines** — score "anomalous *for your peers*" not "high in
   absolute terms" (reuses :mod:`ml.design.peer_fair`). An evader who keeps an absolute
   metric low is still extreme relative to a quiet peer group.
2. **Hidden thresholds** — the decision boundary is never exposed and is jittered with a
   secret per-epoch offset, so the attacker cannot probe for the exact line to sit under.
3. **Randomized review sampling** — a fraction of *below-threshold* items are sampled for
   human review anyway, so "just under the line" is not a safe place to hide.
4. **Diverse ensemble** — rules + unsupervised + supervised + graph. These detectors use
   DIFFERENT signals, so an input crafted to evade one is caught by another. This is the
   load-bearing defense and the one the acceptance test proves.

ALERT-ONLY: every output here is an advisory flag for a human; nothing blocks.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

import numpy as np
import pandas as pd

from ml.base import ReasonCode
from ml.config.seeds import GLOBAL_SEED
from ml.design.peer_fair import peer_relative_unit


# --------------------------------------------------------------------------- #
# 1. Peer-relative baseline (reuse ml.design)                                 #
# --------------------------------------------------------------------------- #
def peer_relative_evasion_baseline(
    scores: pd.Series, peer_groups: pd.Series, *, min_group: int = 3
) -> pd.Series:
    """Re-express raw scores as peer-relative [0,1] (evasion-resistant baseline).

    A would-be evader who lowers their *absolute* score still looks extreme if their peer
    group is quiet. Thin wrapper over :func:`ml.design.peer_fair.peer_relative_unit` so
    L2/L3/L5 all share ONE peer baseline.
    """
    return peer_relative_unit(scores, peer_groups, min_group=min_group)


# --------------------------------------------------------------------------- #
# 2. Hidden / jittered threshold                                              #
# --------------------------------------------------------------------------- #
class HiddenThreshold:
    """A decision threshold that is never exposed and is jittered by a secret offset.

    The public surface only ever answers a *boolean* "does this exceed the (secret)
    threshold?"; it never reveals the threshold value, the score margin, or the jitter.
    The jitter is derived deterministically from a secret key (``os.environ`` /
    constructor) and an epoch, so the attacker cannot reproduce or probe for the boundary.
    """

    def __init__(
        self,
        base_threshold: float = 0.5,
        *,
        jitter: float = 0.05,
        secret: Optional[str] = None,
        epoch: int = 0,
    ) -> None:
        self.base_threshold = float(base_threshold)
        self.jitter = float(jitter)
        # Secret never hardcoded: prefer env, else a process-local random secret.
        self._secret = secret or os.environ.get("HAWKEYE_THRESHOLD_SECRET") or os.urandom(16).hex()
        self.epoch = int(epoch)

    def _offset(self) -> float:
        """Deterministic, secret-keyed jitter in [-jitter, +jitter] — NOT recoverable."""
        h = hashlib.sha256(f"{self._secret}:{self.epoch}".encode()).digest()
        frac = int.from_bytes(h[:8], "big") / float(1 << 64)  # [0,1)
        return (frac * 2.0 - 1.0) * self.jitter

    def effective_threshold(self) -> float:
        """INTERNAL ONLY — the realised threshold. Never return this to a client."""
        return float(np.clip(self.base_threshold + self._offset(), 0.0, 1.0))

    def exceeds(self, score: float) -> bool:
        """The ONLY public answer: above the secret threshold or not (no margin leaked)."""
        return float(score) >= self.effective_threshold()

    def rotate(self, epoch: Optional[int] = None) -> "HiddenThreshold":
        """Advance the epoch so the jittered boundary moves (defeats slow probing)."""
        self.epoch = self.epoch + 1 if epoch is None else int(epoch)
        return self


# --------------------------------------------------------------------------- #
# 3. Randomized review sampling                                               #
# --------------------------------------------------------------------------- #
class RandomizedReviewSampler:
    """Sample a fraction of *below-threshold* items for human review anyway.

    "Just under the line" must not be a safe hiding place: even items the model clears get
    a small random chance of landing in the review queue, so an evader cannot count on
    staying below threshold. Seeded for reproducibility.
    """

    def __init__(self, rate: float = 0.05, *, seed: int = GLOBAL_SEED) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0,1]")
        self.rate = float(rate)
        self._rng = np.random.default_rng(seed)

    def sample_below_threshold(self, entity_ids: Sequence[str], flagged: Sequence[bool]) -> list[str]:
        """Return below-threshold entity ids randomly drawn for extra review."""
        out: list[str] = []
        for eid, is_flagged in zip(entity_ids, flagged):
            if not is_flagged and self._rng.random() < self.rate:
                out.append(str(eid))
        return out

    def expected_coverage(self, n_below: int) -> float:
        """Expected number of below-threshold items pulled for review (capacity planning)."""
        return self.rate * max(int(n_below), 0)


# --------------------------------------------------------------------------- #
# 4. Diverse ensemble (rules + unsupervised + supervised + graph)             #
# --------------------------------------------------------------------------- #
@dataclass
class EnsembleVerdict:
    """Per-entity ensemble outcome: which detectors fired and the fused decision."""

    entity_id: str
    flagged: bool
    detector_scores: dict[str, float] = field(default_factory=dict)
    detectors_fired: list[str] = field(default_factory=list)
    reason_codes: list[ReasonCode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "flagged": self.flagged,
            "detector_scores": {k: round(float(v), 6) for k, v in self.detector_scores.items()},
            "detectors_fired": list(self.detectors_fired),
            "reason_codes": [rc.to_dict() for rc in self.reason_codes],
        }


# A "member" is a callable: entity_features (DataFrame, employee index) -> Series of [0,1]
# scores aligned to that index. Members are deliberately heterogeneous in the SIGNAL they
# use (rule logic / unsupervised density / supervised GBDT / graph structure) so evading
# one does not evade the others.
Member = Callable[[pd.DataFrame], pd.Series]


class DiverseEnsembleDefense:
    """Fuse rules + unsupervised + supervised + graph detectors (evasion resistance).

    The key property (proved by the acceptance test): an input crafted to slip under ONE
    member is flagged by ANOTHER, because each member keys off a different signal. The
    ensemble fires for an entity if ANY member exceeds its (per-member, hidden) threshold —
    union semantics, which is the right default for an alert-only fraud system (recall over
    precision; a human triages).
    """

    def __init__(
        self,
        members: dict[str, Member],
        *,
        member_thresholds: Optional[dict[str, float]] = None,
        peer_groups: Optional[pd.Series] = None,
        secret: Optional[str] = None,
    ) -> None:
        if not members:
            raise ValueError("DiverseEnsembleDefense needs at least one member")
        self.members = dict(members)
        thr = member_thresholds or {}
        # Each member gets its own hidden, jittered threshold (default 0.5).
        self._thresholds = {
            name: HiddenThreshold(thr.get(name, 0.5), secret=secret, epoch=i)
            for i, name in enumerate(self.members)
        }
        self.peer_groups = peer_groups

    def member_names(self) -> list[str]:
        return list(self.members)

    def _peer_adjust(self, scores: pd.Series) -> pd.Series:
        if self.peer_groups is None:
            return scores
        pg = self.peer_groups.reindex(scores.index).fillna("__global__")
        # Peer-relative makes a member resistant to "keep my absolute metric low" evasion.
        return peer_relative_unit(scores, pg)

    def score(self, entity_features: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame of per-member [0,1] scores (index = entity_features.index)."""
        cols: dict[str, pd.Series] = {}
        for name, fn in self.members.items():
            s = pd.to_numeric(pd.Series(fn(entity_features)), errors="coerce")
            s = s.reindex(entity_features.index).fillna(0.0).clip(0.0, 1.0)
            cols[name] = s
        return pd.DataFrame(cols, index=entity_features.index)

    def evaluate(self, entity_features: pd.DataFrame) -> list[EnsembleVerdict]:
        scores = self.score(entity_features)
        verdicts: list[EnsembleVerdict] = []
        for eid in scores.index:
            fired: list[str] = []
            rcs: list[ReasonCode] = []
            dscores: dict[str, float] = {}
            for name in self.members:
                sc = float(scores.at[eid, name])
                dscores[name] = sc
                if self._thresholds[name].exceeds(sc):
                    fired.append(name)
                    rcs.append(ReasonCode(
                        source="rule",
                        code=f"ensemble:{name}",
                        detail=f"{name} detector flagged entity (diverse-ensemble evasion guard)",
                    ))
            verdicts.append(EnsembleVerdict(
                entity_id=str(eid), flagged=bool(fired),
                detector_scores=dscores, detectors_fired=fired, reason_codes=rcs,
            ))
        return verdicts

    def evaluate_one(self, entity_features: pd.DataFrame, entity_id: str) -> EnsembleVerdict:
        for v in self.evaluate(entity_features):
            if v.entity_id == str(entity_id):
                return v
        raise KeyError(f"entity {entity_id!r} not in features")
