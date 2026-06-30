"""DATABASE-9 — retention planner, classification, WORM invariant, fraud carve-out."""

from __future__ import annotations

from pathlib import Path

import pytest
from db.retention.retention_job import (
    WORMViolation,
    build_plan,
    check_worm_safe,
    fraud_carveout_targets,
    load_policies,
)

POLICIES = Path(__file__).resolve().parents[1] / "retention" / "policies.yaml"


@pytest.fixture
def policies():
    return load_policies(POLICIES)


def test_plan_has_hot_cold_archive_for_every_clickhouse_table(policies):
    plan = build_plan(policies)
    ch = [a for a in plan if a.store == "clickhouse"]
    tables = {a.target for a in ch}
    assert {"events", "scores", "alerts", "dispositions", "feature_backfill"} <= tables
    for table in ("events", "alerts"):
        tiers = {a.tier for a in ch if a.target == table and a.op == "move"}
        assert {"cold", "archive"} <= tiers, f"{table} missing hot->cold->archive"


def test_classification_aware_windows(policies):
    plan = build_plan(policies)
    events = next(a for a in plan if a.target == "events" and a.op == "move")
    feat = next(a for a in plan if a.target == "feature_backfill" and a.op == "move")
    assert events.classification == "sensitive"
    assert feat.classification == "operational"


def test_evidence_tables_do_not_auto_expire(policies):
    plan = build_plan(policies)
    for table in ("alerts", "dispositions", "report_outputs"):
        ops = {a.op for a in plan if a.target == table}
        assert "expire" not in ops, f"{table} must not auto-expire (evidence)"


def test_worm_invariant_refuses_early_expire():
    with pytest.raises(WORMViolation):
        check_worm_safe(
            "models", {"object_lock": True, "lock_days": 30, "expire_days": 10}
        )


def test_audit_archive_never_finite_expire():
    with pytest.raises(WORMViolation):
        check_worm_safe(
            "audit-archive",
            {"object_lock": True, "lock_days": 3650, "expire_days": 5000},
        )


def test_audit_archive_policy_is_worm_safe(policies):
    # the shipped policy must itself pass the invariant (build_plan enforces it)
    build_plan(policies)  # raises WORMViolation if any locked bucket is unsafe
    aa = policies["stores"]["object_store"]["buckets"]["audit-archive"]
    assert aa["object_lock"] is True
    assert aa["expire_days"] is None


def test_fraud_carveout_present_and_longer(policies):
    fc = fraud_carveout_targets(policies)
    assert fc["applies_when"].startswith("disposition.outcome")
    # carve-out hold must exceed the default sensitive alert window (2920d)
    assert fc["min_retain_days"] > 2920
    assert "clickhouse.dispositions" in fc["covers"]


def test_models_lifecycle_archives_old_versions(policies):
    plan = build_plan(policies)
    noncurrent = [a for a in plan if a.target == "models" and a.tier == "noncurrent"]
    assert noncurrent, "old model versions must be lifecycle-expired (Part 23.3)"
