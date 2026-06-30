"""Shadow scoring (ML-18; blueprint Part 18).

A CHALLENGER model scores live traffic in parallel with the champion but emits NO alerts —
its scores are only logged for offline champion/challenger comparison. This is the safe way
to evaluate a candidate on production traffic before any promotion. The hard contract:
``alerts_emitted == 0`` for a shadow run (asserted by callers and tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.eval import average_precision


@dataclass
class ShadowResult:
    model_version: str
    scores: list[float]
    entity_ids: list[str]
    alerts_emitted: int = 0  # INVARIANT: always 0 for shadow.
    champion_auprc: Optional[float] = None
    challenger_auprc: Optional[float] = None
    logged: int = 0

    @property
    def emits_no_alerts(self) -> bool:
        return self.alerts_emitted == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "n_scored": len(self.scores),
            "alerts_emitted": self.alerts_emitted,
            "emits_no_alerts": self.emits_no_alerts,
            "champion_auprc": self.champion_auprc,
            "challenger_auprc": self.challenger_auprc,
            "logged": self.logged,
        }


class ShadowScorer:
    """Score live traffic with a challenger, LOG only — emit zero alerts."""

    def __init__(self, challenger: Any, *, sink: Optional[list] = None) -> None:
        self.challenger = challenger
        self.sink = sink if sink is not None else []

    def _score(self, X) -> np.ndarray:
        if hasattr(self.challenger, "predict_proba"):
            p = self.challenger.predict_proba(X)
        else:
            p = self.challenger.score_samples(X)
        return np.asarray(p, dtype=float).ravel()

    def shadow_score(
        self,
        X: pd.DataFrame,
        *,
        y: Optional[pd.Series] = None,
        champion_scores: Optional[np.ndarray] = None,
    ) -> ShadowResult:
        """Score X with the challenger and LOG; emit NO alerts (alerts_emitted stays 0)."""
        p = self._score(X)
        ids = [str(i) for i in X.index]
        # log scores to the sink (this is the ONLY side effect — no alert emission)
        for eid, s in zip(ids, p):
            self.sink.append(
                {
                    "entity_id": eid,
                    "shadow_score": float(s),
                    "model_version": getattr(
                        self.challenger, "model_version", "unknown"
                    ),
                    "alert": False,
                }
            )

        champ_ap = chal_ap = None
        if y is not None and int(np.asarray(y).sum()) > 0:
            chal_ap = average_precision(y, p)
            if champion_scores is not None:
                champ_ap = average_precision(y, champion_scores)

        return ShadowResult(
            model_version=getattr(self.challenger, "model_version", "unknown"),
            scores=[float(x) for x in p],
            entity_ids=ids,
            alerts_emitted=0,  # by construction: shadow NEVER emits alerts
            champion_auprc=champ_ap,
            challenger_auprc=chal_ap,
            logged=len(ids),
        )


__all__ = ["ShadowScorer", "ShadowResult"]
