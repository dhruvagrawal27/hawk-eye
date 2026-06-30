"""Hawk-Eye ML workstream (Laptop 02).

The multi-layer detection model stack and its MLOps spine:
L2 unsupervised UEBA, L3 supervised GBDT, L4 sequence, L5 graph, L6 fusion;
honest non-point-adjust evaluation; training/retraining/inference pipelines;
MLflow champion/challenger MLOps; drift; fairness/bias; adversarial robustness;
and the TEE-attested LLM narrative gateway with deterministic fallback.

Golden rules (prompts/02_ML.md): ALERT-ONLY (score+explain, never auto-block);
ON-PREM + SYNTHETIC ONLY; VALIDATE-AGAINST-BLUEPRINT; NOTHING-DROPPED; STAY-IN-LANE;
HONEST-EVALUATION (never point-adjust; baselines first; split by time).

All pandas dtype checks use ``pd.api.types.*`` (never ``np.issubdtype`` on a Series
dtype) so the code runs on both pandas 2.3.x and 3.0.x (see CONTEXT.md 2026-06-30 DATA note).
"""

__version__ = "0.1.0"

GLOBAL_SEED = 1405  # matches DATA's SimConfig.seed for reproducible cross-workstream runs
