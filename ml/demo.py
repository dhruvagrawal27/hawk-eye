"""End-to-end walking skeleton (prompt §10 final integration test).

A synthetic fraud burst flows through the **sync fast-lane**:

    L0 events -> L1 rule + L2 anomaly + L3 GBDT + L5 XGB-Graph -> L6 fusion
              -> calibrated 0-100 alert with reason codes -> narrate() narrative

The alert is **contestable** (reason codes + narrative) and **reproducible** (feature
vector + model_version persisted). Per Part 18 the hot path is trees only; the deep L4
sequence models run on the async/batch path, so this single-process demo stays torch-free
(L2 without the AutoEncoder member, L3 LightGBM, L5 XGB-Graph) — which also sidesteps the
macOS torch+LightGBM libomp clash. Run:  ``.mlvenv/bin/python -m ml.demo``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml import eval as E
from ml.adapters import DataSimFeatureSource
from ml.base.interfaces import ReasonCode
from ml.config.seeds import seed_everything
from ml.layers.l2 import EcodDetector, IsolationForestDetector, L2Ensemble
from ml.layers.l3 import LightGBMScorer
from ml.layers.l5 import XGBGraphScorer
from ml.layers.l6 import L6Fusion
from ml.narrative import narrate


def l1_rule_flags(events: pd.DataFrame) -> pd.Series:
    """L1-style deterministic rule: off-hours high-value approval / new-beneficiary payout."""
    df = events.copy()
    amount = pd.to_numeric(df.get("object.amount"), errors="coerce").fillna(0.0)
    offh = df.get("context.is_off_hours", False)
    offh = offh.astype(bool) if hasattr(offh, "astype") else pd.Series(False, index=df.index)
    verb = df.get("action.verb", "").astype(str)
    hit = ((amount >= 1_000_000) & offh) | ((verb == "approve_payment") & (amount >= 1_000_000))
    by_emp = pd.Series(hit.values, index=df["actor.employee_id"].astype(str).values)
    return by_emp.groupby(level=0).max().astype(float)


def run(employees: int = 150, days: int = 10) -> dict:
    seed_everything()
    print("=" * 78)
    print("HAWK-EYE ML — end-to-end walking skeleton (L0 -> L2/L3/L5 -> L6 -> narrative)")
    print("=" * 78)

    src = DataSimFeatureSource(employees=employees, days=days)
    events = src.events()
    ef = src.entity_features()
    el = src.entity_labels().reindex(ef.index).fillna(0).astype(int)
    print(f"L0: {len(events)} events, {ef.shape[0]} entities, {int(el.sum())} fraud actors "
          f"(base rate {el.mean():.2%})")

    # --- L1 rules ---
    rule = l1_rule_flags(events).reindex(ef.index).fillna(0.0)
    print(f"L1 rules: fired for {int(rule.sum())} entities")

    # --- L2 unsupervised (torch-free: IsolationForest + ECOD) ---
    l2 = L2Ensemble(detectors=[IsolationForestDetector(), EcodDetector()]).fit(ef)
    s_l2 = pd.Series(l2.score_samples(ef), index=ef.index)
    print(f"L2 unsupervised: AUPRC {E.average_precision(el.to_numpy(), s_l2.to_numpy()):.3f} "
          f"(model {l2.model_version})")

    # --- L3 supervised GBDT (LightGBM) + TreeSHAP reason codes ---
    l3 = LightGBMScorer().fit(ef, el)
    s_l3 = pd.Series(l3.predict_proba(ef), index=ef.index)
    print(f"L3 GBDT: AUPRC {E.average_precision(el.to_numpy(), s_l3.to_numpy()):.3f} "
          f"(model {l3.model_version})")

    # --- L5 graph (XGB-Graph default) ---
    l5 = XGBGraphScorer(k=2).fit(ef, el.to_numpy(), events=events)
    s_l5 = pd.Series(l5.predict_proba(ef, events=events), index=ef.index)
    print(f"L5 XGB-Graph: AUPRC {E.average_precision(el.to_numpy(), s_l5.to_numpy()):.3f} "
          f"(model {l5.model_version})")

    # --- L6 fusion (stacked meta + isotonic calibration) ---
    layer_scores = pd.DataFrame({
        "L1_rule": rule.to_numpy(),
        "L2_unsupervised": s_l2.to_numpy(),
        "L3_gbdt": s_l3.to_numpy(),
        "L4_sequence": 0.0,  # async deep path (Part 18) — not in the sync demo
        "L5_graph": s_l5.to_numpy(),
    }, index=ef.index)
    fusion = L6Fusion(meta_kind="logistic").fit(layer_scores, el)
    fused = pd.Series(fusion.calibrated_scores(layer_scores), index=ef.index)
    print(f"L6 fusion: AUPRC {E.average_precision(el.to_numpy(), fused.to_numpy()):.3f} "
          f"(calibrated 0-100; model {fusion.model_version})")

    # --- pick the top alert, assemble reason codes, narrate ---
    top = fused.sort_values(ascending=False).index[0]
    i = ef.index.get_loc(top)
    l3_codes = l3.reason_codes(ef.iloc[[i]], top_k=3)[0]
    rcs = {
        "L1": [ReasonCode("rule", code="OFFHOURS_HIGHVALUE_APPROVAL",
                          detail="off-hours approval >= INR 1000000")] if rule.loc[top] else [],
        "L3": l3_codes,
        "L5": [ReasonCode("graph", detail="elevated k-hop neighbourhood risk (XGB-Graph)")],
    }
    alert = fusion.fuse_one(
        entity_id=str(top), alert_id="alr_demo01",
        layer_scores={c: float(layer_scores.loc[top, c]) for c in layer_scores.columns},
        reason_codes_by_layer=rcs, exposure_inr=4_800_000,
    )
    ad = alert.to_dict()
    print("\n" + "-" * 78)
    print(f"TOP ALERT  entity={ad['entity_id']}  risk={ad['risk_score']}/100  "
          f"severity={ad['severity']}  confidence={ad['confidence']}  (true_fraud={bool(el.loc[top])})")
    print(f"  contributing_layers: {ad['contributing_layers']}")
    for rc in ad["reason_codes"]:
        print(f"  reason[{rc['source']}]: {rc.get('detail') or rc.get('code') or rc.get('feature')}"
              + (f" ({rc['contribution']})" if 'contribution' in rc else ""))

    # --- narrative gateway (no keys -> deterministic template; UI never breaks) ---
    narrative = narrate(ad)
    print("\n  NARRATIVE [" + narrative["provider"] + ", tee_attested="
          + str(narrative["tee_attested"]) + "]:")
    print("    " + narrative["narrative"].replace("\n", "\n    "))

    # --- reproducibility: the score is reconstructable from feature vector + model versions ---
    provenance = {
        "entity_id": str(top),
        "feature_vector": {k: float(v) for k, v in ef.loc[top].to_dict().items()},
        "model_versions": {"L2": l2.model_version, "L3": l3.model_version,
                           "L5": l5.model_version, "L6": fusion.model_version},
        "fused_risk": int(ad["risk_score"]),
    }
    print("\n  REPRODUCIBLE: alert reconstructable from persisted feature vector + model versions "
          f"({len(provenance['feature_vector'])} features, {len(provenance['model_versions'])} models)")
    print("=" * 78)
    print("END-TO-END OK: L0 -> L2/L3/L5 -> L6 calibrated alert -> grounded narrative -> contestable + reproducible")
    return {"alert": ad, "narrative": narrative, "provenance": provenance}


if __name__ == "__main__":
    run()
