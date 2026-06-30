"""Attack-on-the-system SIEM detectors (PLATFORM-21, blueprint Part 19.5).

"Treat the detection platform like any other crown-jewel asset in your SIEM." Detects the
FOUR attack signatures Part 19.5 calls out, against the system's OWN audit/access events:
  1. extraction-pattern querying  (model inversion/extraction recon)
  2. abnormal label edits         (EDD feedback-label poisoning)
  3. training-data anomalies      (training-set poisoning)
  4. config/threshold changes     (blinding the detector)

Canonical rules live as Sigma YAML in security/siem/detection-rules/. This module is the
runnable engine the test suite (tests/security/test_siem_rules.py) exercises; in prod these
map to SIEM (Splunk/Sentinel/OpenSearch) correlation rules over the audit stream.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Detection:
    rule: str
    severity: str
    matched: bool
    detail: str


# Thresholds (tune per environment).
EXTRACTION_QUERY_THRESHOLD = 100   # inference calls / actor / 5-min window
LABEL_EDIT_THRESHOLD = 20          # label edits / actor / day
TRAIN_ANOMALY_Z = 4.0              # z-score of a training-batch feature distribution shift


def detect_extraction(events: list[dict]) -> Detection:
    """High-volume inference querying by one actor = model extraction/inversion recon."""
    by_actor: dict[str, int] = {}
    for e in events:
        if e.get("action") == "model_infer":
            by_actor[e.get("actor", "?")] = by_actor.get(e.get("actor", "?"), 0) + 1
    worst = max(by_actor.items(), key=lambda kv: kv[1], default=("none", 0))
    hit = worst[1] >= EXTRACTION_QUERY_THRESHOLD
    return Detection("ML_MODEL_EXTRACTION_PATTERN", "high", hit,
                     f"{worst[0]} made {worst[1]} inference calls (>={EXTRACTION_QUERY_THRESHOLD})")


def detect_label_edits(events: list[dict]) -> Detection:
    """An actor editing a disproportionate share of EDD labels = feedback poisoning."""
    by_actor: dict[str, int] = {}
    for e in events:
        if e.get("action") == "label_edit":
            by_actor[e.get("actor", "?")] = by_actor.get(e.get("actor", "?"), 0) + 1
    worst = max(by_actor.items(), key=lambda kv: kv[1], default=("none", 0))
    hit = worst[1] >= LABEL_EDIT_THRESHOLD
    return Detection("ABNORMAL_LABEL_EDITS", "high", hit,
                     f"{worst[0]} edited {worst[1]} labels (>={LABEL_EDIT_THRESHOLD}) — review for poisoning")


def detect_training_anomaly(events: list[dict]) -> Detection:
    """A training batch whose feature distribution shifts sharply = training-data poisoning."""
    worst_z = 0.0
    detail = "no training batches"
    for e in events:
        if e.get("action") == "training_batch":
            z = float(e.get("dist_shift_z", 0.0))
            if z > worst_z:
                worst_z, detail = z, f"batch {e.get('batch_id','?')} dist-shift z={z}"
    return Detection("TRAINING_DATA_ANOMALY", "high", worst_z >= TRAIN_ANOMALY_Z, detail)


def detect_config_change(events: list[dict]) -> Detection:
    """Any change to rules/thresholds/model config = could blind detection (four-eyes required)."""
    changes = [e for e in events if e.get("action") in ("threshold_change", "rule_change", "config_change")]
    unapproved = [e for e in changes if not e.get("four_eyes_approved")]
    hit = len(unapproved) > 0
    detail = (f"{len(unapproved)} unapproved config/threshold change(s): "
              f"{[e.get('target') for e in unapproved]}" if hit else f"{len(changes)} change(s), all four-eyes approved")
    return Detection("UNAPPROVED_CONFIG_THRESHOLD_CHANGE", "critical", hit, detail)


DETECTORS = [detect_extraction, detect_label_edits, detect_training_anomaly, detect_config_change]


def run_all(events: list[dict]) -> list[Detection]:
    return [d(events) for d in DETECTORS]
