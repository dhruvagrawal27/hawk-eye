"""IEEE-CIS Fraud (Vesta, 2019) loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): real-world card-not-present, ~590k txns, 300+ features, ~3.5% fraud.
Use it to prototype the *tabular supervised layer (L3)* and learn feature-engineering
patterns (Kaggle winners used gradient boosting + heavy FE, AUC ~= 0.91).

Mapping: this is a TABULAR dataset -> documented FEATURE-SPACE form (a pandas DataFrame),
NOT L0 behavioural events. The label column is `isFraud`.

Leakage caveats:
- `TransactionID` is an identifier, not a feature -> drop before training (DATA-24).
- `TransactionDT` is a time offset -> use it for the TEMPORAL split, do not feed as a raw
  feature without care (it trivially separates train/test if leaked).
- No drop-in pre-trained model exists for the bank (Part 5.3); transfer/prototyping only.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from data.config import SimConfig

LABEL_COL = "isFraud"
TS_COL = "TransactionDT"
ID_COLS = ("TransactionID",)


class IeeeCisLoader:
    name = "ieee_cis"
    purpose = "tabular supervised L3 (IEEE-CIS Vesta)"
    leakage_caveats = "TransactionID is an id (drop); TransactionDT is time (use for split)."
    label_col = LABEL_COL
    ts_col = TS_COL

    def load(self, path: str) -> pd.DataFrame:
        """Load real `train_transaction.csv` (optionally merged with identity) if present;
        otherwise a tiny synthetic stand-in DataFrame in the same feature-space shape."""
        if path and os.path.isfile(path):
            df = pd.read_csv(path)
            return df
        return self.synthetic()

    def synthetic(self, cfg: Optional[SimConfig] = None) -> pd.DataFrame:
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        n = 400
        fraud = rng.random(n) < 0.035  # ~3.5% like Vesta
        df = pd.DataFrame({
            "TransactionID": np.arange(n),
            "TransactionDT": np.sort(rng.integers(0, 600_000, n)),
            "TransactionAmt": rng.gamma(2.0, 50.0, n).round(2),
            "card1": rng.integers(1000, 20000, n),
            "C1": rng.integers(0, 50, n),
            "D1": rng.integers(0, 400, n),
            "isFraud": fraud.astype(int),
        })
        # make fraud mildly separable (but not perfectly -> no leakage)
        df.loc[df["isFraud"] == 1, "TransactionAmt"] *= 1.6
        return df


def demo() -> pd.DataFrame:
    return IeeeCisLoader().synthetic()
