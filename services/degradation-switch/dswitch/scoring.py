"""Reference scoring + risk fusion for the degradation switch (PLATFORM-4).

Two modes (Part 18 / Part 30.1):
  - "full"        : ML serving healthy -> fuse L1 rule hits + L2-L6 layer scores.
  - "rules_only"  : ML serving down or forced -> L1 rules ONLY; event is marked for
                    re-scoring (hawkeye.rescore) so nothing is silently dropped.

Fusion is an interpretable weighted combine (Layer-6 transparent ensemble, Part 18)
so the final 0-100 score stays explainable to audit. This is the platform's
*continuity* scorer; BACKEND owns the production fusion/serving (Part 18) — the switch
defers to it when healthy and only owns the fallback decision + routing.

GOLDEN RULE 1 (ALERT-ONLY): this returns an alert (score + reasons) for a human to
triage. It never returns or triggers an action. status is always "open".
"""

from __future__ import annotations

import hashlib
from typing import Optional

from . import rules

ALERT_THRESHOLD = 50  # final 0-100 at/above which an alert is raised
LAYER_WEIGHTS = {  # transparent fusion weights over per-layer anomaly scores
    "L2_unsupervised": 0.20,
    "L3_gbdt": 0.30,
    "L4_sequence": 0.15,
    "L5_graph": 0.20,
}
RULES_WEIGHT = 0.35  # weight given to the strongest L1 rule hit in full mode


def _alert_id(event_id: str) -> str:
    return "alr_" + hashlib.sha256(event_id.encode()).hexdigest()[:6]


def _severity(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 65:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def score_event(
    ev: dict,
    mode: str,
    layer_scores: Optional[dict[str, float]] = None,
) -> Optional[dict]:
    """Score one L0 event. Returns an L6-alert dict (BACKEND.md §2) or None.

    `layer_scores` are per-layer anomaly scores in [0,1] (e.g. fetched from serving);
    ignored in rules_only mode.
    """
    rule_hits = rules.evaluate(ev)
    contributing: list[str] = []
    reason_codes: list[dict] = []

    rules_component = 0.0
    if rule_hits:
        contributing.append("L1_rules")
        reason_codes.extend(
            {k: v for k, v in rc.items() if k != "severity"} for rc in rule_hits
        )
        rules_component = max(rc["severity"] for rc in rule_hits) / 100.0

    if mode == "rules_only":
        final01 = rules_component
        marked_for_rescore = True
    else:
        ls = layer_scores or {}
        fused = RULES_WEIGHT * rules_component
        wsum = RULES_WEIGHT if rule_hits else 0.0
        for layer, w in LAYER_WEIGHTS.items():
            if layer in ls:
                fused += w * float(ls[layer])
                wsum += w
                contributing.append(layer)
                reason_codes.append(
                    {
                        "source": "model",
                        "layer": layer,
                        "contribution": round(float(ls[layer]), 3),
                    }
                )
        final01 = fused / wsum if wsum else rules_component
        marked_for_rescore = False

    risk = int(round(min(1.0, max(0.0, final01)) * 100))
    if risk < ALERT_THRESHOLD:
        return None

    actor = ev.get("actor") or {}
    obj = ev.get("object") or {}
    confidence = (
        0.6
        if mode == "rules_only"
        else round(min(0.95, 0.6 + 0.1 * len(contributing)), 2)
    )
    return {
        "alert_id": _alert_id(ev.get("event_id", "evt_unknown")),
        "entity_id": actor.get("employee_id", "EMP-unknown"),
        "risk_score": risk,
        "severity": _severity(risk),
        "confidence": confidence,
        "status": "open",  # ALERT-ONLY: human decides (PLATFORM-37 gate)
        "created_ts": ev.get("ts"),
        "contributing_layers": contributing,
        "reason_codes": reason_codes,
        "exposure_inr": int(obj.get("amount") or 0),
        "pii_tokenized": True,
        "scoring_mode": mode,  # provenance: full vs degraded
        "marked_for_rescore": marked_for_rescore,  # re-score when ML serving recovers
        "source_event_id": ev.get("event_id"),
    }
