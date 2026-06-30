"""Deterministic stand-in models (# STUB: ML — signed ONNX L2/L3 artifacts).

Until ML delivers signed ONNX artifacts, these deterministic scorers honour the model-serving
contract (BACKEND.md §6): input = assembled feature vector, output = per-layer score in 0–1. They
are monotone in the obvious risk directions (off-hours ↑, new-beneficiary latency ↓ ⇒ risk ↑,
amount z-score ↑, SoD flag ⇒ risk ↑) so the worked-burst and directional tests behave like the
real trees will. Swapping in ML's ONNX needs no contract change — only ``runtime.load`` changes.
"""

from __future__ import annotations

import math

STUB_VERSIONS = {
    "L2_unsupervised": "l2_isoforest@stub-2026.06.30",
    "L3_gbdt": "l3_lightgbm@stub-2026.06.30",
    "L4_sequence": "l4_usad@stub-2026.06.30",
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _signals(fv: dict) -> dict:
    off = 1.0 if fv.get("is_off_hours") else 0.0
    amount_z = float(fv.get("amount_zscore", 0.0) or 0.0)
    amount_z = max(-4.0, min(4.0, amount_z))
    latency = fv.get("minutes_since_new_beneficiary")
    # Lower latency between new-beneficiary and payment ⇒ higher risk.
    lat_risk = 0.0
    if latency is not None:
        lat_risk = max(0.0, 1.0 - float(latency) / 120.0)
    sod = 1.0 if (fv.get("maker_checker_same_actor") or fv.get("maker_checker_pair_isolated")) else 0.0
    privileged = 1.0 if fv.get("privileged_session") else 0.0
    return {"off": off, "amount_z": amount_z, "lat_risk": lat_risk, "sod": sod, "priv": privileged}


def score_l2_unsupervised(fv: dict) -> float:
    s = _signals(fv)
    z = 0.9 * s["off"] + 0.45 * s["amount_z"] + 1.1 * s["lat_risk"] + 0.4 * s["priv"] - 0.6
    return round(_sigmoid(z), 4)


def score_l3_gbdt(fv: dict) -> float:
    s = _signals(fv)
    z = 1.0 * s["off"] + 0.7 * s["amount_z"] + 1.6 * s["lat_risk"] + 1.4 * s["sod"] - 1.0
    return round(_sigmoid(z), 4)


def score_l4_sequence(fv: dict) -> float:
    s = _signals(fv)
    z = 0.8 * s["off"] + 1.2 * s["lat_risk"] + 0.6 * s["priv"] - 0.8
    return round(_sigmoid(z), 4)


SCORERS = {
    "L2_unsupervised": score_l2_unsupervised,
    "L3_gbdt": score_l3_gbdt,
    "L4_sequence": score_l4_sequence,
}
