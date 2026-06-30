# Hawk-Eye detection stack — decision summary (ML-9)

> The "simple-beats-deep" cheat-sheet (blueprint Part 17.A) + the one-screen
> layer→default-model mapping (Part 20.8). Every rigorous benchmark (ADBench,
> Grinsztajn, TimeEval, GADBench) points the same way: **tree-based & simple methods
> win or tie on accuracy while crushing deep models on cost, latency, explainability**
> for this problem class. Lead with them; add deep sequence/graph surgically.

## Per-layer reference (Part 17.A — job / models / labels needed)
| Layer | Job | Default model(s) | Labels needed | Explainer |
|---|---|---|---|---|
| **L1 Rules/BRE** | Encode SoD/toxic-combos + known typologies | Deterministic rules (Drools/Flink-CEP) | none | rule provenance |
| **L2 Unsupervised** | Cold-start UEBA, novel-scheme safety net | **Isolation Forest** (+ ECOD/COPOD, Autoencoder) via PyOD | none | per-feature reconstruction error |
| **L3 Supervised** | Precision engine once labels exist | **LightGBM** (+ CatBoost, XGBoost) | yes (EDD/known/weak/synthetic) | **TreeSHAP** |
| **L4 Sequence** | Low-and-slow / session anomalies (the warning layer) | **simple baselines first** (windowed PCA/IF); TranAD/USAD only if they beat them | unsup; LAXCAT needs labels | LAXCAT attention |
| **L5 Graph** | Collusion / mule-rings / maker-checker rings | **XGB-Graph / RF-Graph** (k-hop → GBDT); GraphSAGE inductive | semi (PU) | GNNExplainer |
| **L6 Fusion** | One calibrated alert per entity | **stacked meta-learner + isotonic calibration** | yes | assembled reason codes |

## One-screen layer → default-model mapping (Part 20.8)
| Layer | Use this (default) | Strong alternatives / when | Avoid as primary | Anchor benchmark |
|---|---|---|---|---|
| L1 | Deterministic BRE | Flink-CEP streaming rules | pure-rules-only | event-pipeline studies |
| L2 | **Isolation Forest** (+ECOD/COPOD; AE for explanations) | AE for non-linear normal | DeepSVDD/DAGMM | **ADBench** |
| L3 | **LightGBM** | CatBoost (high-cardinality), XGBoost (robust) | TabNet/FT-Transformer | **Grinsztajn** |
| L4 | **Simple baselines first**; TranAD/USAD only if they beat them | TranAD low-latency deep; DeepLog for logs | any deep chosen on PA-inflated scores | **Wu&Keogh, Kim'22, TimeEval** |
| L5 | **XGB-Graph / RF-Graph** | GraphSAGE (inductive); CARE/PC/BWGNN (camouflage) | vanilla GCN/GIN under heterophily | **GADBench** |
| Explain | **TreeSHAP** + counterfactuals + rule provenance | LAXCAT session attention | SHAP interaction values real-time | XAI-fraud reviews |
| L6 | **Stacked meta-learner + isotonic calibration** | weighted average (simplest) | uncalibrated raw scores | stacking + calibration lit |

## Escalation discipline
Ship **L1 + L2 + dashboard first** (value in weeks, no labels). Add **L3** once the EDD
loop yields labels. Add **L4/L5 only when justified** — "work smartly, don't go all-in."

## Alert-only invariant
No model output blocks money or auto-classifies fraud. Every alert is **contestable**:
it carries reason codes + a narrative (Part 29.2). See `alert_only_contract.py`.
