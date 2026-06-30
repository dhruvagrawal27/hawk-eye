"""SIEM detection-rule tests (PLATFORM-21, Part 19.5). Each of the 4 attack signatures
must fire; benign activity must not. Also asserts the Sigma rule files exist."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "security" / "siem"))
import detect  # noqa: E402

RULES_DIR = ROOT / "security" / "siem" / "detection-rules"


def test_extraction_pattern_fires():
    events = [{"action": "model_infer", "actor": "EMP-mal"} for _ in range(150)]
    d = detect.detect_extraction(events)
    assert d.matched and d.rule == "ML_MODEL_EXTRACTION_PATTERN"


def test_abnormal_label_edits_fire():
    events = [{"action": "label_edit", "actor": "EMP-mal"} for _ in range(25)]
    assert detect.detect_label_edits(events).matched


def test_training_data_anomaly_fires():
    events = [{"action": "training_batch", "batch_id": "b1", "dist_shift_z": 5.2}]
    assert detect.detect_training_anomaly(events).matched


def test_unapproved_config_change_fires():
    events = [{"action": "threshold_change", "target": "L3_threshold", "four_eyes_approved": False}]
    assert detect.detect_config_change(events).matched


def test_benign_activity_does_not_fire():
    benign = (
        [{"action": "model_infer", "actor": "svc-backtest"} for _ in range(5)]
        + [{"action": "label_edit", "actor": "u_labeler"} for _ in range(3)]
        + [{"action": "training_batch", "batch_id": "b2", "dist_shift_z": 0.4}]
        + [{"action": "threshold_change", "target": "L3", "four_eyes_approved": True}]
    )
    assert not any(d.matched for d in detect.run_all(benign))


def test_all_four_signatures_detected_together():
    attack = (
        [{"action": "model_infer", "actor": "EMP-mal"} for _ in range(150)]
        + [{"action": "label_edit", "actor": "EMP-mal"} for _ in range(25)]
        + [{"action": "training_batch", "batch_id": "b", "dist_shift_z": 6.0}]
        + [{"action": "rule_change", "target": "SoD", "four_eyes_approved": False}]
    )
    fired = [d.rule for d in detect.run_all(attack) if d.matched]
    assert len(fired) == 4


def test_sigma_rule_files_present():
    rules = list(RULES_DIR.glob("*.yml"))
    assert len(rules) >= 4
