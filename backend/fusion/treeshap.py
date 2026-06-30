"""Inline plain TreeSHAP reason codes (BACKEND-12, blueprint Part 18.1 l.585).

Plain TreeSHAP only — **no interaction values** inline (those are ~quadratic in features and belong
offline). # STUB: ML (TreeSHAP over the real L3 GBDT). This deterministic attributor mirrors the
L3 stub's weights so the top contributing features are sensible and stable; ML swaps in real
TreeSHAP outputs without changing the reason-code assembler.
"""

from __future__ import annotations

# Feature name ⇄ (signal extractor, weight) mirroring serving.stubs L3 weights.
_FEATURE_WEIGHTS = [
    ("new_beneficiary_to_payment_latency_min", "lat_risk", 1.6),
    ("maker_checker_pair_frequency_30d", "sod", 1.4),
    ("off_hours_activity_flag", "off", 1.0),
    ("amount_zscore", "amount_z", 0.7),
    ("privileged_session_flag", "priv", 0.6),
]


def _signals(fv: dict) -> dict:
    off = 1.0 if fv.get("is_off_hours") else 0.0
    amount_z = max(0.0, min(4.0, float(fv.get("amount_zscore", 0.0) or 0.0)))
    latency = fv.get("minutes_since_new_beneficiary")
    lat_risk = 0.0 if latency is None else max(0.0, 1.0 - float(latency) / 120.0)
    sod = (
        1.0
        if (fv.get("maker_checker_same_actor") or fv.get("maker_checker_pair_isolated"))
        else 0.0
    )
    priv = 1.0 if fv.get("privileged_session") else 0.0
    return {"off": off, "amount_z": amount_z / 4.0, "lat_risk": lat_risk, "sod": sod, "priv": priv}


def top_features(feature_vector: dict, k: int = 4) -> list[dict]:
    """Return the top-k SHAP-style contributions as ``[{feature, contribution}]`` (desc)."""
    sig = _signals(feature_vector)
    raw = [(name, sig.get(key, 0.0) * weight) for name, key, weight in _FEATURE_WEIGHTS]
    positive = [(n, c) for n, c in raw if c > 0]
    total = sum(c for _, c in positive) or 1.0
    contribs = sorted(
        ({"feature": n, "contribution": round(c / total, 2)} for n, c in positive),
        key=lambda d: d["contribution"],
        reverse=True,
    )
    return contribs[:k]
