"""Fixed-seed configuration for reproducibility (ML-1; blueprint Part 22.4).

Every run is reproducible: a single seed drives numpy, Python's `random`, and
(if installed) PyTorch. `seeded_rng` returns an isolated Generator so a component
can be deterministic without touching global state.
"""
from __future__ import annotations

import os
import random
from typing import Optional

import numpy as np

from ml._optional import optional_import

GLOBAL_SEED = 1405  # matches DATA's SimConfig.seed (CONTEXT.md) for cross-workstream parity


def seed_everything(seed: int = GLOBAL_SEED, *, deterministic_torch: bool = True) -> int:
    """Seed Python, numpy, and (if present) torch. Returns the seed used."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch = optional_import("torch")
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():  # pragma: no cover - no GPU in CI
            torch.cuda.manual_seed_all(seed)
        if deterministic_torch:
            try:
                torch.use_deterministic_algorithms(True, warn_only=True)
            except Exception:  # pragma: no cover - older torch
                pass
    return seed


def seeded_rng(seed: Optional[int] = None) -> np.random.Generator:
    """Return an isolated numpy Generator (default: GLOBAL_SEED)."""
    return np.random.default_rng(GLOBAL_SEED if seed is None else seed)
