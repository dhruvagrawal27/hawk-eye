"""Reason-code assembler (BACKEND-12, blueprint Part 18.1 l.585 / 11).

Assembles the alert's ``reason_codes`` from three provenances, in priority order:
  1. rule provenance  (source=rule)  — from the L1 engine hits + SoD flags
  2. SHAP top features (source=shap)  — plain TreeSHAP over the L3 GBDT
  3. graph evidence    (source=graph) — from the async L5 graph path (when present)
Plus sequence attention (source=sequence) when L4 contributed. This is exactly the explanation
panel's data (rule + SHAP + attention + graph).
"""

from __future__ import annotations

from fusion.treeshap import top_features


def assemble(
    *,
    rule_reason_codes: list[dict],
    feature_vector: dict,
    graph_evidence: list[str] | None = None,
    sequence_attention: list[dict] | None = None,
    shap_k: int = 4,
) -> list[dict]:
    codes: list[dict] = []

    # 1) Rule provenance (verbatim codes from L1).
    for rc in rule_reason_codes:
        codes.append({"source": "rule", "code": rc.get("code"), "detail": rc.get("detail")})

    # 2) SHAP top features.
    for feat in top_features(feature_vector, k=shap_k):
        codes.append(
            {"source": "shap", "feature": feat["feature"], "contribution": feat["contribution"]}
        )

    # 3) Graph evidence (async L5 upgrade path).
    for ev in graph_evidence or []:
        codes.append({"source": "graph", "detail": ev})

    # 4) Sequence attention (L4), when present.
    for step in sequence_attention or []:
        codes.append(
            {"source": "sequence", "detail": f"step {step.get('step')}: {step.get('verb')}",
             "contribution": step.get("weight")}
        )

    return codes
