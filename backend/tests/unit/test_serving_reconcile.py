"""M1.4 — serving risk_tier: seeded tiers, registry↔authoritative reconcile, tier-gated
promote/load. FREE-AI/MRMF: the served models carry a risk tier, drift is caught, and a
tier-1-critical model can't be promoted without independent sign-off."""

from __future__ import annotations

import pytest

from serving.loader import ModelLoader, SignatureError
from serving.reconcile import RegistryInventoryReconciler
from serving.registry import (
    TIER_CRITICAL,
    TIER_HIGH,
    TIER_MODERATE,
    ArtifactMeta,
    LocalRegistry,
    normalize_layer,
)


def test_seeded_artifacts_carry_risk_tier():
    reg = LocalRegistry()
    tiers = {a.model_id: a.risk_tier for a in reg.list()}
    assert tiers["l3_lightgbm"] == TIER_CRITICAL
    assert tiers["l6_meta"] == TIER_CRITICAL
    assert tiers["l2_isoforest"] == TIER_HIGH
    assert tiers["l4_usad"] == TIER_MODERATE


def test_reconcile_healthy_on_default_registry():
    report = RegistryInventoryReconciler().reconcile(LocalRegistry())
    assert report.healthy
    assert report.to_dict()["healthy"] is True


def test_reconcile_detects_tier_mismatch():
    reg = LocalRegistry()
    reg.get("l3_lightgbm").risk_tier = TIER_MODERATE  # wrong tier
    report = RegistryInventoryReconciler().reconcile(reg)
    assert not report.healthy
    assert any(m["model_id"] == "l3_lightgbm" for m in report.tier_mismatch)


def test_reconcile_detects_missing_tier():
    reg = LocalRegistry()
    reg.get("l2_isoforest").risk_tier = None
    report = RegistryInventoryReconciler().reconcile(reg)
    assert "l2_isoforest" in report.tier_missing


def test_reconcile_detects_untracked_layer():
    reg = LocalRegistry()
    reg._artifacts.append(
        ArtifactMeta(model_id="l9_experimental", layer="L9_x", version="v1", stage="Production")
    )
    report = RegistryInventoryReconciler().reconcile(reg)
    assert "l9_experimental" in report.untracked


def test_reconcile_detects_version_drift():
    reg = LocalRegistry()
    report = RegistryInventoryReconciler().reconcile(reg, expected_versions={"L3": "expected-9.9"})
    assert any(d["layer"] == "L3" for d in report.version_drift)


def test_reconcile_ignores_non_production_artifacts():
    reg = LocalRegistry()
    # The l3_catboost challenger has a mismatched-looking tier context but is not Production.
    report = RegistryInventoryReconciler().reconcile(reg)
    assert all(m["model_id"] != "l3_catboost" for m in report.tier_mismatch)


def test_tier_gate_blocks_critical_promote_without_signoff():
    reg = LocalRegistry()
    meta, blockers = reg.set_stage_with_tier_gate(
        "l3_catboost", "challenger-2026.06.30", "Production"
    )
    assert meta is None and blockers  # critical model needs sign-off
    assert reg.get("l3_catboost", "challenger-2026.06.30").stage == "Challenger"  # unchanged


def test_tier_gate_allows_critical_promote_with_signoff():
    reg = LocalRegistry()
    meta, blockers = reg.set_stage_with_tier_gate(
        "l3_catboost", "challenger-2026.06.30", "Production", signoff_by="EMP-tl01"
    )
    assert meta is not None and not blockers
    assert meta.stage == "Production"


def test_tier_gate_allows_moderate_promote_without_signoff():
    reg = LocalRegistry()
    # Stage the L4 (moderate) artifact to Staging then back to Production without sign-off.
    meta, blockers = reg.set_stage_with_tier_gate("l4_usad", "stub-2026.06.30", "Staging")
    assert not blockers
    meta, blockers = reg.set_stage_with_tier_gate("l4_usad", "stub-2026.06.30", "Production")
    assert not blockers and meta.stage == "Production"


def test_load_tier_check_rejects_high_tier_unsigned_allows_low_tier_unsigned():
    reg = LocalRegistry()
    reg.get("l3_lightgbm").signature = "tampered"  # critical + invalid signature
    reg.get("l4_usad").signature = "tampered"  # moderate + invalid signature
    loader = ModelLoader(registry=reg, require_signature=True)

    with pytest.raises(SignatureError):
        loader.load_production_with_tier_check("L3_gbdt")  # critical must be signed

    low = loader.load_production_with_tier_check("L4_sequence")  # moderate may load unsigned
    assert low is not None and low.model_id == "l4_usad"


def test_normalize_layer():
    assert normalize_layer("L3_gbdt") == "L3"
    assert normalize_layer("L6_fusion") == "L6"


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
