"""L6 fusion orchestrator (ML-7): per-layer scores + rule hits -> one calibrated alert.

Ties the stacked meta-learner + isotonic calibration + reason-code assembler into a single
``L6Fusion`` that produces a BACKEND.md §2 Alert per entity. The ONLINE fusion service is
BACKEND's (Part 18); ML ships this artifact + the offline reason-code assembler.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from ml.base.interfaces import Alert, ReasonCode
from ml.layers.l6.calibration import RiskCalibrator, severity_confidence
from ml.layers.l6.reason_codes import assemble_reason_codes, build_alert
from ml.layers.l6.stacked_meta import (
    LAYER_COLUMNS,
    StackedMetaLearner,
    assemble_layer_matrix,
)

_LAYER_LABEL = {
    "L1_rule": "L1_rules",
    "L2_unsupervised": "L2_unsupervised",
    "L3_gbdt": "L3_gbdt",
    "L4_sequence": "L4_sequence",
    "L5_graph": "L5_graph",
}


class L6Fusion:
    """Stacked fusion + calibration + reason-code assembly -> Alert (one per entity)."""

    def __init__(
        self,
        meta_kind: str = "logistic",
        calibration: str = "isotonic",
        contributing_threshold: float = 0.5,
    ) -> None:
        self.meta = StackedMetaLearner(kind=meta_kind)
        self.calibrator = RiskCalibrator(method=calibration)
        self.contributing_threshold = contributing_threshold

    @property
    def model_version(self) -> str:
        return self.meta.model_version

    def fit(self, layer_scores, y) -> "L6Fusion":
        Xdf = (
            layer_scores
            if isinstance(layer_scores, pd.DataFrame)
            else assemble_layer_matrix(layer_scores)
        )
        yv = np.asarray(y).astype(int).ravel()
        self.meta.fit(Xdf, yv)
        self.calibrator.fit(self.meta.predict_proba(Xdf), yv)
        return self

    def calibrated_scores(self, layer_scores) -> np.ndarray:
        Xdf = (
            layer_scores
            if isinstance(layer_scores, pd.DataFrame)
            else assemble_layer_matrix(layer_scores)
        )
        return self.calibrator.calibrate(self.meta.predict_proba(Xdf))

    def fuse_one(
        self,
        *,
        entity_id: str,
        alert_id: str,
        layer_scores: dict[str, float],
        reason_codes_by_layer: Optional[dict[str, Sequence[ReasonCode]]] = None,
        exposure_inr: Optional[int] = None,
        created_ts: Optional[str] = None,
    ) -> Alert:
        row = assemble_layer_matrix({k: [float(v)] for k, v in layer_scores.items()})
        cal_p = float(self.calibrator.calibrate(self.meta.predict_proba(row))[0])
        _, confidence = severity_confidence(cal_p)

        contributing = [
            _LAYER_LABEL[c]
            for c in LAYER_COLUMNS
            if float(layer_scores.get(c, 0.0)) >= self.contributing_threshold
        ]
        rc_map = dict(reason_codes_by_layer or {})
        rc_map["L6_meta"] = self.meta.reason_codes(row, top_k=3)[0]
        reasons = assemble_reason_codes(rc_map)
        return build_alert(
            alert_id=alert_id,
            entity_id=entity_id,
            calibrated_prob=cal_p,
            confidence=confidence,
            contributing_layers=contributing or ["L6_fusion"],
            reason_codes=reasons,
            exposure_inr=exposure_inr,
            created_ts=created_ts,
        )

    def fuse_batch(
        self,
        layer_scores: pd.DataFrame,
        entity_ids: Sequence[str],
        *,
        alert_prefix: str = "alr",
    ) -> list[Alert]:
        cal = self.calibrator.calibrate(self.meta.predict_proba(layer_scores))
        contribs = self.meta.reason_codes(layer_scores)
        alerts = []
        for i, (eid, p) in enumerate(zip(entity_ids, cal)):
            _, conf = severity_confidence(float(p))
            row = layer_scores.iloc[i]
            contributing = [
                _LAYER_LABEL[c]
                for c in LAYER_COLUMNS
                if float(row.get(c, 0.0)) >= self.contributing_threshold
            ]
            alerts.append(
                build_alert(
                    alert_id=f"{alert_prefix}_{i:06d}",
                    entity_id=str(eid),
                    calibrated_prob=float(p),
                    confidence=conf,
                    contributing_layers=contributing or ["L6_fusion"],
                    reason_codes=assemble_reason_codes({"L6_meta": contribs[i]}),
                )
            )
        return alerts
