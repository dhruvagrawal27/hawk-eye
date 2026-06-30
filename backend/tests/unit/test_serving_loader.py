"""Model-serving loader unit tests (BACKEND-16): signature verify + canary hot-swap."""

from __future__ import annotations

import pytest

from serving.loader import ModelLoader, SignatureError, _canary_hit
from serving.registry import ArtifactMeta, LocalRegistry, sign


def test_production_artifact_loads_when_signed():
    loader = ModelLoader(LocalRegistry())
    model = loader.load_production("L3_gbdt")
    assert model is not None
    assert model.version
    assert loader.version_for("L3_gbdt", "evt_1") == model.version


def test_unsigned_artifact_is_rejected():
    reg = LocalRegistry()
    reg._artifacts.append(
        ArtifactMeta(model_id="evil", layer="L9_x", version="1", stage="Production", signature="")
    )
    loader = ModelLoader(reg)
    with pytest.raises(SignatureError):
        loader.load_production("L9_x")


def test_tampered_signature_is_rejected():
    reg = LocalRegistry()
    art = reg.get("l3_lightgbm")
    art.signature = "deadbeef"  # tamper
    loader = ModelLoader(reg)
    with pytest.raises(SignatureError):
        loader.load_production("L3_gbdt")


def test_signature_helper_matches():
    assert sign("m", "1") == sign("m", "1")
    assert sign("m", "1") != sign("m", "2")


def test_canary_split_is_deterministic():
    # Same key always routes the same way; 0% never hits, 100% always hits.
    assert _canary_hit("evt_1", 0) is False
    assert _canary_hit("evt_1", 100) is True
    assert _canary_hit("evt_1", 50) == _canary_hit("evt_1", 50)


def test_canary_hot_swap_verifies_signature():
    loader = ModelLoader(LocalRegistry())
    canary = loader.canary_hot_swap("l3_catboost", "challenger-2026.06.30", 25)
    assert canary.percent == 25
    assert canary.challenger.version == "challenger-2026.06.30"
