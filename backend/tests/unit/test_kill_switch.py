"""M2.4 — per-model kill-switch: state store, runtime skip/degrade, L1-survives, route RBAC+audit."""

from __future__ import annotations

from serving.loader import ModelLoader
from serving.model_state import MODEL_STATE, ModelStateStore
from serving.registry import LocalRegistry
from serving.runtime import InferenceRuntime


def test_state_store_disable_enable():
    s = ModelStateStore()
    assert not s.is_disabled("l3_lightgbm")
    s.disable("l3_lightgbm", actor="EMP-x", reason="drift", ts="2026-07-01T00:00:00Z")
    assert s.is_disabled("l3_lightgbm")
    s.enable("l3_lightgbm", actor="EMP-x", ts="2026-07-01T00:05:00Z")
    assert not s.is_disabled("l3_lightgbm")


def test_runtime_skips_disabled_layer_and_keeps_others():
    reg = LocalRegistry()
    rt = InferenceRuntime(loader=ModelLoader(registry=reg))
    fv = {"amount": 1.0}
    base = rt.score(fv, layers=["L2_unsupervised", "L3_gbdt"])
    assert "L3_gbdt" in base.scores  # healthy first

    MODEL_STATE.disable("l3_lightgbm", actor="EMP-x", reason="halt", ts="t")
    try:
        degraded = rt.score(fv, layers=["L2_unsupervised", "L3_gbdt"])
        assert "L3_gbdt" not in degraded.scores  # disabled → skipped
        assert "L3_gbdt" in degraded.degraded_layers
        assert "L2_unsupervised" in degraded.scores  # other layers still serve
    finally:
        MODEL_STATE.reset()


def test_disable_all_ml_degrades_without_crash():
    reg = LocalRegistry()
    rt = InferenceRuntime(loader=ModelLoader(registry=reg))
    for mid in ("l2_isoforest", "l3_lightgbm"):
        MODEL_STATE.disable(mid, actor="x", reason="halt", ts="t")
    try:
        res = rt.score({"amount": 1.0}, layers=["L2_unsupervised", "L3_gbdt"])
        assert res.scores == {}  # all ML skipped — never crashes; L1 (elsewhere) still alerts
    finally:
        MODEL_STATE.reset()


def test_disable_route_rbac_and_audit(client, auth):
    # RBAC: view-only role can't disable; RM (relationship_manager) lacks train_deploy_models.
    assert client.post("/api/v1/models/l3_lightgbm/disable", json={"reason": "drift"}).status_code == 401
    assert (
        client.post(
            "/api/v1/models/l3_lightgbm/disable",
            headers=auth("analyst"),
            json={"reason": "drift"},
        ).status_code
        == 403
    )
    # Data Science Lead (model_engineer) may halt.
    r = client.post(
        "/api/v1/models/l3_lightgbm/disable",
        headers=auth("model_engineer"),
        json={"reason": "PR-AUC dropped in prod"},
    )
    assert r.status_code == 200 and r.json()["disabled"] is True

    st = client.get("/api/v1/models/l3_lightgbm/state", headers=auth("model_engineer"))
    assert st.status_code == 200 and st.json()["disabled"] is True

    en = client.post("/api/v1/models/l3_lightgbm/enable", headers=auth("model_engineer"))
    assert en.status_code == 200 and en.json()["disabled"] is False

    from app.audit.writer import AUDIT

    actions = {e.action for e in AUDIT.all()}
    assert "model.disable" in actions and "model.enable" in actions


def test_disable_unknown_model_404(client, auth):
    assert (
        client.post(
            "/api/v1/models/nope/disable", headers=auth("model_engineer"), json={"reason": "halt"}
        ).status_code
        == 404
    )
