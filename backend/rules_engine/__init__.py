"""L1 Rules / BRE + SoD toxic-combination engine (BACKEND-5/6/7).

Deterministic Layer-1 baseline: necessary-but-insufficient, versioned, hot-reloadable, cold-start
safe. Decoupled from the API app (operates on dict events + a feature dict) so it can run in the
Rust/Python hot path, in batch, and in tests.
"""

from rules_engine.context import RuleContext
from rules_engine.engine import DEFAULT_ENGINE, EvalResult, RulesEngine
from rules_engine.rule import RuleConfig, RuleHit
from rules_engine.sod_matrix import DEFAULT_SOD_MATRIX, SoDFlag, SoDMatrix, SoDResult

__all__ = [
    "RuleContext",
    "RulesEngine", "EvalResult", "DEFAULT_ENGINE",
    "RuleConfig", "RuleHit",
    "SoDMatrix", "SoDResult", "SoDFlag", "DEFAULT_SOD_MATRIX",
]
