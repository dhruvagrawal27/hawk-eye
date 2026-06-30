"""ULB / European Credit-Card Fraud (2013) loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): 284,807 txns, 492 frauds (0.172%), PCA-anonymised features V1..V28
+ Time + Amount + Class. THE extreme-imbalance test bed -> tune PR-AUC and resampling
(connects to DATA-11 subsampling 1:3-1:10 + class weights).

Mapping: TABULAR -> documented FEATURE-SPACE form (DataFrame). Label column is `Class`.

Leakage caveats:
- Features are already PCA components (anonymised) -> no obvious leaky raw field, but
  `Time` is a seconds offset: use it for the TEMPORAL split, not as a naive feature.
- No drop-in pre-trained model for the bank (Part 5.3); imbalance-handling prototype only.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from data.config import SimConfig

LABEL_COL = "Class"
TS_COL = "Time"


class UlbLoader:
    name = "ulb"
    purpose = "extreme-imbalance test bed (ULB Credit-Card 0.172% fraud)"
    leakage_caveats = "PCA features (anonymised); Time is offset -> use for split only."
    label_col = LABEL_COL
    ts_col = TS_COL

    def load(self, path: str) -> pd.DataFrame:
        if path and os.path.isfile(path):
            return pd.read_csv(path)
        return self.synthetic()

    def synthetic(self, cfg: Optional[SimConfig] = None) -> pd.DataFrame:
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        n = 1000
        # ~0.2% fraud to mirror the extreme imbalance (at least 1 positive at small N)
        n_fraud = max(2, int(round(n * 0.002)))
        cls = np.zeros(n, dtype=int)
        cls[rng.choice(n, size=n_fraud, replace=False)] = 1
        cols = {f"V{i}": rng.normal(0, 1, n) for i in range(1, 29)}
        cols["Time"] = np.sort(rng.integers(0, 172_800, n))
        cols["Amount"] = rng.gamma(1.5, 40.0, n).round(2)
        cols["Class"] = cls
        df = pd.DataFrame(cols)
        df.loc[df["Class"] == 1, "V1"] += 3.0  # mild signal, not perfect separation
        return df


def demo() -> pd.DataFrame:
    return UlbLoader().synthetic()
