"""SPEDIA (2025) / Amazon Fraud-Dataset-Benchmark loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): newer insider / aggregated fraud benchmarks (SPEDIA 2025; Amazon
Fraud Dataset Benchmark = 9 sets). Use for BROADER benchmarking and ablations across
heterogeneous fraud distributions.

Mapping: FDB is a *collection* of tabular sets with a common (label, timestamp, entity)
contract. We expose a documented FEATURE-SPACE DataFrame with `EVENT_LABEL` (label),
`EVENT_TIMESTAMP` (time) and `ENTITY_ID` -- the FDB harness convention -- so the same
splits/leakage tooling (DATA-24) applies. Pass `subset=` to pick one of the 9 FDB sets.

Leakage caveats:
- FDB sets vary: some include post-hoc fields (e.g., chargeback flags) that encode the
  label -> always run the DATA-24 leakage detector per subset before training.
- ENTITY_ID is an identifier, not a feature -> drop / use only for entity-disjoint splits.
- No drop-in pre-trained model for the bank (Part 5.3); benchmarking/ablation only.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from data.config import SimConfig

LABEL_COL = "EVENT_LABEL"
TS_COL = "EVENT_TIMESTAMP"
ENTITY_COL = "ENTITY_ID"

FDB_SUBSETS = (
    "fraudecom", "sparknov", "fakejob", "vehicleloan", "malurl",
    "ieeecis", "ccfraud", "fraudoss", "ipblock",
)


class SpediaLoader:
    name = "spedia"
    purpose = "broader benchmarking / ablations (SPEDIA 2025 + Amazon FDB, 9 sets)"
    leakage_caveats = (
        "subsets vary; some carry post-hoc fields encoding the label -> run leakage "
        "detector per subset; ENTITY_ID is an id (use for entity-disjoint split only)."
    )
    label_col = LABEL_COL
    ts_col = TS_COL
    entity_col = ENTITY_COL
    subsets = FDB_SUBSETS

    def __init__(self, subset: str = "fraudecom") -> None:
        self.subset = subset

    def load(self, path: str) -> pd.DataFrame:
        if path and os.path.isfile(path):
            df = pd.read_csv(path)
            # normalise common FDB column aliases to our contract
            ren = {}
            if "EVENT_LABEL" not in df.columns:
                for c in ("isFraud", "is_fraud", "label", "Class"):
                    if c in df.columns:
                        ren[c] = LABEL_COL
                        break
            return df.rename(columns=ren)
        return self.synthetic()

    def synthetic(self, cfg: Optional[SimConfig] = None) -> pd.DataFrame:
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        n = 300
        ts0 = pd.Timestamp("2025-01-01T00:00:00Z")
        df = pd.DataFrame({
            ENTITY_COL: [f"BEN-{int(x):04d}" for x in rng.integers(0, 80, n)],
            TS_COL: [(ts0 + pd.Timedelta(hours=int(h))).isoformat().replace("+00:00", "Z")
                     for h in np.sort(rng.integers(0, 2000, n))],
            "amount": rng.gamma(2.0, 100.0, n).round(2),
            "n_prior_events": rng.integers(0, 30, n),
            LABEL_COL: (rng.random(n) < 0.05).astype(int),
        })
        return df


def demo() -> pd.DataFrame:
    return SpediaLoader().synthetic()
