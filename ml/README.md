# Hawk-Eye — ML workstream (Laptop 02)

The multi-layer detection model stack and its MLOps spine. **Alert-only** (score + explain,
never auto-block), **on-prem + synthetic-only**, **honest evaluation** (never point-adjust;
simple baselines first; split by time).

## Run it (from repo root)
```bash
# ML venv is python3.13 at .mlvenv (repo target is 3.12 but no 3.12 interpreter is available)
.mlvenv/bin/python -m pytest tests/ml/ -q            # full ML test suite
.mlvenv/bin/python -m ml.tests.run                   # stdlib runner (no pytest needed)
.mlvenv/bin/python -m ml.demo                         # end-to-end L0->L2->L3->...->L6->narrative
```
`pip install -e ml/[all]` is optional; every module imports on numpy/pandas/scikit-learn
alone via `ml/_optional.py` guards, and the heavy detectors are REAL where the lib is present.

## Layout (owner: ML / branch `hawk-eye/ml`)
| Dir | Tasks | What |
|---|---|---|
| `_optional.py`, `config/`, `base/` | ML-1 | optional-dep registry, fixed seeds, `BaseDetector/BaseScorer` + reason-code/alert contracts |
| `adapters/` | ML-1 | `FeatureSource` (DATA seam: real simulator + synthetic fallback), model/label stores |
| `eval/` | ML-2 | non-PA metrics (PR-AUC, precision@k, range/affiliation-aware PR, VUS-PR), temporal/entity splits, leakage guards |
| `layers/l2..l6/` | ML-3..7 | L2 unsupervised, L3 GBDT+TreeSHAP, L4 sequence, L5 graph, L6 fusion |
| `strategies/` | ML-8 | imbalance, PU/semi-supervised, transfer learning |
| `design/` | ML-9 | peer-fair + alert-only contract + decision summary |
| `narrative/` | ML-10..13 | TEE-LLM gateway (NEAR AI->Groq->deterministic), attestation, audit, guardrails, `POST /narratives` |
| `pipelines/` | ML-14..19 | training DAG, per-layer training, feedback loop, repro, inference, backtest |
| `mlops/` | ML-20..24 | MLflow registry/inventory, champion-challenger, drift, governance/MRM |
| `fairness/` | ML-25..26 | disparate-impact metrics, mitigations, proxy detection, feedback-loop trap |
| `robustness/` | ML-27 | evasion/poisoning/inversion/explanation defenses |
| `metrics/` | ML-29 | operational/business metrics (incl. RBI TAT) |
| `tests/`, `../tests/ml/` | ML-28 | behavioral/metamorphic/directional/regression/drift/fairness-gated/leakage |

## Status
See `docs/laptops/02-ml.md` for per-task REAL/SCAFFOLD/MOCK status and blueprint validations.
SCAFFOLD = NEAR AI/Groq live calls + TEE attestation (need real keys/hardware). MOCK = the
independent model-validation human sign-off.
