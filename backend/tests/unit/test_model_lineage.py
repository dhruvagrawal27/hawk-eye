"""Phase 6 — Governance & trust. The explanation now carries per-layer model lineage: which model
version produced each contributing layer's score, plus its governance posture (stage / MRMF risk
tier / signature / SoD sign-off) — the regulator-facing 'which model fired this, who signed it'."""

from __future__ import annotations


def test_explanation_carries_model_lineage(client, auth):
    r = client.get("/api/v1/explanations/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    lineage = r.json()["model_lineage"]
    assert lineage, "expected per-layer model lineage"

    by_layer = {e["layer"]: e for e in lineage}
    # L6 fusion is always present; the worked burst also contributes L3.
    assert "L6_fusion" in by_layer
    assert "L3_gbdt" in by_layer

    for e in lineage:
        assert e["model_id"] and e["version"] and e["stage"]
        assert isinstance(e["signed"], bool)

    # the ML layers are signed + carry an MRMF risk tier; L1 rules are deterministic + four-eyes.
    assert by_layer["L6_fusion"]["signed"] is True
    assert by_layer["L6_fusion"]["risk_tier"]  # non-empty tier
    assert by_layer["L3_gbdt"]["approving_reviewer"]
    if "L1_rule" in by_layer:
        assert by_layer["L1_rule"]["risk_tier"] == "deterministic"
