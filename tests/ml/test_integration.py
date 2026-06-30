"""End-to-end integration test (prompt §10 final integration).

Drives the full walking skeleton (ml.demo.run): L0 -> L1/L2/L3/L5 -> L6 fusion ->
calibrated alert -> grounded narrative -> contestable + reproducible. Torch-free sync
fast-lane, so it runs clean in one process.
"""

from __future__ import annotations


def test_end_to_end_walking_skeleton():
    from ml.demo import run

    result = run(employees=120, days=8)
    assert set(result) >= {"alert", "narrative", "provenance"}

    alert = result["alert"]
    for key in (
        "alert_id",
        "entity_id",
        "risk_score",
        "severity",
        "confidence",
        "contributing_layers",
        "reason_codes",
        "pii_tokenized",
    ):
        assert key in alert
    assert 0 <= alert["risk_score"] <= 100
    assert alert["severity"] in ("low", "medium", "high")  # BACKEND.md §2 contract
    assert alert["pii_tokenized"] is True
    # alert is contestable: it carries reason codes (Part 29.2)
    assert alert["reason_codes"]
    assert all(
        rc["source"] in ("rule", "shap", "graph", "attention")
        for rc in alert["reason_codes"]
    )

    narrative = result["narrative"]
    assert narrative["provider"] in ("near_ai", "groq", "template")
    assert narrative["narrative"]  # UI never breaks: always some narrative

    # reproducible: reconstructable from persisted feature vector + model versions
    prov = result["provenance"]
    assert prov["feature_vector"] and prov["model_versions"]
    assert {"L2", "L3", "L5", "L6"} <= set(prov["model_versions"])


def test_fast_lane_is_torch_free():
    """The sync fast-lane (demo) must not load torch (Part 18 hot-path = trees only)."""
    import sys

    import ml.demo  # noqa: F401  (importing the demo module must not load torch)
    from ml.layers.l5 import XGBGraphScorer  # noqa: F401

    assert (
        "torch" not in sys.modules
    ), "fast-lane imports must stay torch-free (libomp safety)"
