"""DATABASE-7/8 — registry serializer round-trip + signing + verify + access-log."""

from __future__ import annotations

import numpy as np
import onnxruntime as ort
import pytest
from onnx import TensorProto, helper
from registry.artifacts.serializer import (
    ModelArtifact,
    bundle_files,
    load_chain,
    save_chain,
)
from registry.artifacts.store import LocalArtifactStore
from registry.mlflow.access_log import ListEmitter
from registry.mlflow.config import GovernanceError, Registry
from registry.mlflow.load_verify import secure_load, verify_artifact
from registry.mlflow.signing import SignatureError, sign_bundle, verify_bundle


def _linear_onnx() -> bytes:
    """A trivial but real ONNX model: y = x·W + b."""
    w = helper.make_tensor("W", TensorProto.FLOAT, [3, 1], [0.5, -0.2, 1.0])
    b = helper.make_tensor("b", TensorProto.FLOAT, [1], [0.1])
    xin = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3])
    yout = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1])
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["x", "W"], ["xw"]),
            helper.make_node("Add", ["xw", "b"], ["y"]),
        ],
        "lin",
        [xin],
        [yout],
        [w, b],
    )
    m = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 9
    return m.SerializeToString()


def _predict(onnx_bytes: bytes):
    sess = ort.InferenceSession(onnx_bytes, providers=["CPUExecutionProvider"])
    return sess.run(None, {"x": np.array([[1.0, 2.0, 3.0]], dtype=np.float32)})[0]


def _tree_artifact() -> ModelArtifact:
    return ModelArtifact(
        layer="L3",
        model="lightgbm_gbdt",
        version="v1.4.2",
        onnx=_linear_onnx(),
        native={"booster.txt": b"tree=0\nleaf_value=0.1 0.2\n"},
        transform_chain={
            "scaler.joblib": b"<<scaler-bytes>>",
            "encoder.joblib": b"<<enc>>",
        },
        calibrator=b"<<isotonic-calibrator-joblib>>",
    )


def _net_artifact() -> ModelArtifact:
    return ModelArtifact(
        layer="L4",
        model="laxcat",
        version="v0.3.0",
        onnx=_linear_onnx(),
        checkpoint=b"<<pytorch-checkpoint-bytes>>",
        transform_chain={"window_scaler.joblib": b"<<ws>>"},
        calibrator=b"<<calib>>",
    )


def test_tree_chain_round_trip_identical_predictions(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    art = _tree_artifact()
    before = _predict(art.onnx)
    save_chain(store, art)
    loaded = load_chain(store, "L3", "lightgbm_gbdt", "v1.4.2")
    after = _predict(loaded.onnx)
    assert np.allclose(before, after)
    # whole transform chain reloaded together
    assert set(loaded.native) == {"booster.txt"}
    assert set(loaded.transform_chain) == {"scaler.joblib", "encoder.joblib"}
    assert loaded.calibrator == art.calibrator


def test_net_chain_round_trip_onnx_plus_checkpoint(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    art = _net_artifact()
    save_chain(store, art)
    loaded = load_chain(store, "L4", "laxcat", "v0.3.0")
    assert loaded.onnx is not None
    assert loaded.checkpoint == art.checkpoint
    assert set(loaded.transform_chain) == {"window_scaler.joblib"}


def test_sign_then_verify_accepts(tmp_path):
    art = _tree_artifact()
    sig = sign_bundle(bundle_files(art))
    assert verify_bundle(bundle_files(art), sig) is True


@pytest.mark.parametrize(
    "tamper_file",
    [
        "model.onnx",
        "booster.txt",
        "transform_chain/scaler.joblib",
        "calibrator.joblib",
        "metadata.json",
    ],
)
def test_signature_rejects_tamper_in_any_file(tmp_path, tamper_file):
    art = _tree_artifact()
    art.metadata = {"dataset_hash": "sha256:x"}
    files = bundle_files(art)
    sig = sign_bundle(files)
    # mutate one file → signature must fail
    files = dict(files)
    files[tamper_file] = files[tamper_file] + b"\x00tamper"
    assert verify_bundle(files, sig) is False


def test_register_writes_six_field_metadata_and_signature(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    emit = ListEmitter()
    reg = Registry(store=store, emitter=emit)
    ref = reg.register(
        _tree_artifact(),
        dataset_hash="sha256:abc",
        params={"num_leaves": 64},
        metrics={"pr_auc": 0.91},
        training_code_commit="9f34901",
        approver="EMP-co02",
        feature_set_version="fs-2026.06",
    )
    loaded = load_chain(store, "L3", "lightgbm_gbdt", "v1.4.2")
    for fld in (
        "dataset_hash",
        "params",
        "metrics",
        "training_code_commit",
        "approver",
        "signature",
    ):
        assert loaded.metadata.get(fld), f"missing metadata field {fld}"
    assert loaded.signature is not None
    assert verify_artifact(loaded) is True
    assert [r["action"] for r in emit.records] == ["model_version_register"]
    assert ref == "L3/lightgbm_gbdt/v1.4.2"


def test_register_rejects_missing_metadata(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    reg = Registry(store=store, emitter=ListEmitter())
    with pytest.raises(GovernanceError):
        reg.register(
            _tree_artifact(),
            dataset_hash="",
            params={},
            metrics={},
            training_code_commit="",
            approver="",
        )


def test_promote_enforces_sod_and_logs(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    emit = ListEmitter()
    reg = Registry(store=store, emitter=emit)
    reg.register(
        _tree_artifact(),
        dataset_hash="sha256:a",
        params={"x": 1},
        metrics={"m": 1},
        training_code_commit="c",
        approver="EMP-co02",
    )
    # four-eyes: promoter must differ from approver
    with pytest.raises(GovernanceError):
        reg.promote(
            "L3",
            "lightgbm_gbdt",
            "v1.4.2",
            "Production",
            promoter="EMP-x",
            approver="EMP-x",
        )
    rec = reg.promote(
        "L3",
        "lightgbm_gbdt",
        "v1.4.2",
        "Production",
        promoter="EMP-me01",
        approver="EMP-co02",
    )
    assert rec["stage"] == "Production"
    assert "model_version_promote" in [r["action"] for r in emit.records]


def test_secure_load_accepts_valid_rejects_tampered(tmp_path):
    store = LocalArtifactStore(tmp_path / "models")
    emit = ListEmitter()
    reg = Registry(store=store, emitter=emit)
    reg.register(
        _tree_artifact(),
        dataset_hash="sha256:a",
        params={"x": 1},
        metrics={"m": 1},
        training_code_commit="c",
        approver="EMP-co02",
    )

    art = secure_load("L3", "lightgbm_gbdt", "v1.4.2", store=store, emitter=emit)
    assert art.onnx is not None
    # every load emits an access-log event (extraction-theft mitigation)
    assert "registry_load" in [r["action"] for r in emit.records]

    # tamper the stored onnx → load must be REJECTED, and the attempt still logged
    key = "L3/lightgbm_gbdt/v1.4.2/model.onnx"
    raw = bytearray(store.get(key))
    raw[10] ^= 0xFF
    store.put(key, bytes(raw))
    n_before = len(emit.records)
    with pytest.raises(SignatureError):
        secure_load("L3", "lightgbm_gbdt", "v1.4.2", store=store, emitter=emit)
    assert len(emit.records) == n_before + 1  # the rejected load is audited too


def test_corrupt_metadata_json_audited_and_rejected_as_signature_error(tmp_path):
    # A metadata.json corrupted to INVALID JSON must still (a) emit an access-log
    # event and (b) reject via SignatureError — never a raw JSONDecodeError that
    # escapes the audit trail and breaks BACKEND's serving loader (Part 19.2).
    store = LocalArtifactStore(tmp_path / "models")
    emit = ListEmitter()
    reg = Registry(store=store, emitter=emit)
    reg.register(
        _tree_artifact(),
        dataset_hash="sha256:a",
        params={"x": 1},
        metrics={"m": 1},
        training_code_commit="c",
        approver="EMP-co02",
    )
    store.put("L3/lightgbm_gbdt/v1.4.2/metadata.json", b"{ this is : not valid json")
    n_before = len(emit.records)
    with pytest.raises(SignatureError):
        secure_load("L3", "lightgbm_gbdt", "v1.4.2", store=store, emitter=emit)
    assert len(emit.records) == n_before + 1  # the tampered-load attempt is audited
