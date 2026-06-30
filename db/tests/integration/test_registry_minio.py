"""DATABASE-7/8 integration — register/promote/load a model in the MinIO `models` bucket.

Requires the storage compose up (MinIO + object-locked `models` bucket).
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _linear_onnx():
    from onnx import TensorProto, helper

    w = helper.make_tensor("W", TensorProto.FLOAT, [2, 1], [1.0, 1.0])
    xin = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 2])
    yout = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1])
    graph = helper.make_graph(
        [helper.make_node("MatMul", ["x", "W"], ["y"])], "lin", [xin], [yout], [w]
    )
    m = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 9
    return m.SerializeToString()


def test_register_promote_load_in_minio(minio_client):
    pytest.importorskip("onnx")
    from registry.artifacts.serializer import ModelArtifact
    from registry.artifacts.store import MinioArtifactStore
    from registry.mlflow.access_log import ListEmitter
    from registry.mlflow.config import Registry

    store = MinioArtifactStore(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9001"),
        access_key=os.getenv("MINIO_ROOT_USER", "hawkeye"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw"),
    )
    emit = ListEmitter()
    reg = Registry(store=store, emitter=emit)
    art = ModelArtifact(
        layer="L3",
        model="lightgbm_gbdt",
        version="vint01",
        onnx=_linear_onnx(),
        native={"booster.txt": b"tree=0\n"},
        transform_chain={"scaler.joblib": b"<<s>>"},
        calibrator=b"<<c>>",
    )
    ref = reg.register(
        art,
        dataset_hash="sha256:int",
        params={"n": 1},
        metrics={"m": 1},
        training_code_commit="abc",
        approver="EMP-co02",
    )
    assert ref == "L3/lightgbm_gbdt/vint01"
    reg.promote(
        "L3",
        "lightgbm_gbdt",
        "vint01",
        "Production",
        promoter="EMP-me01",
        approver="EMP-co02",
    )
    loaded = reg.load("L3", "lightgbm_gbdt", "vint01")
    assert loaded.onnx is not None and loaded.calibrator == b"<<c>>"
    actions = [r["action"] for r in emit.records]
    assert {"model_version_register", "model_version_promote", "registry_load"} <= set(
        actions
    )
