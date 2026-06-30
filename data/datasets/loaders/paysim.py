"""PaySim mobile-money simulator loader (DATA-12, Part 5.3 / 17.B).

Status: REAL.

Purpose (Part 5.3): 6.3M synthetic transfers/cash-outs with injected fraud. Use it for
SCALE / THROUGHPUT testing of the streaming pipeline -- NOT a model-quality benchmark.

*** BALANCE-LEAKAGE CAVEAT (Part 5.3, Part 14) ***
PaySim's balance columns (`oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`,
`newbalanceDest`) LEAK the label: a fraudulent TRANSFER/CASH_OUT empties the origin
account, so newbalanceOrig==0 is almost a perfect predictor. Any model that "wins" on
PaySim is usually just reading the leak. These columns MUST be removed before training
(see DATA-24 remove_leaky_features); this loader exposes `LEAKY_COLS` for that detector.
Synthetic-only -> unrealistically easy; never treat PaySim AUC as production quality.

Mapping: TABULAR -> FEATURE-SPACE DataFrame (label `isFraud`); also `to_l0()` to map rows
to L0 transaction events for the streaming scale test.

No drop-in pre-trained model exists for the bank (Part 5.3); PaySim is scale-testing only.
"""
from __future__ import annotations

import os
from typing import Optional

import numpy as np
import pandas as pd

from data.config import SimConfig, make_id, CURRENCY_DEFAULT
from data.schemas import L0Event, Actor, Action, ObjectRef, Context

LABEL_COL = "isFraud"
TS_COL = "step"
# The fields that encode the label -> the leakage detector / remover targets these.
LEAKY_COLS = ("oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest")


class PaySimLoader:
    name = "paysim"
    purpose = "streaming scale/throughput test (PaySim) -- NOT a quality benchmark"
    leakage_caveats = (
        "balance columns leak the label (newbalanceOrig==0 ~ perfect predictor); "
        f"drop {LEAKY_COLS} before training (DATA-24)."
    )
    label_col = LABEL_COL
    ts_col = TS_COL
    leaky_cols = LEAKY_COLS

    def load(self, path: str) -> pd.DataFrame:
        if path and os.path.isfile(path):
            return pd.read_csv(path)
        return self.synthetic()

    def synthetic(self, cfg: Optional[SimConfig] = None, n: int = 600) -> pd.DataFrame:
        cfg = cfg or SimConfig()
        rng = np.random.default_rng(cfg.seed)
        types = rng.choice(["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT"], size=n)
        amount = rng.gamma(2.0, 5000.0, n).round(2)
        old_org = rng.gamma(2.0, 20000.0, n).round(2)
        is_fraud = ((types == "TRANSFER") | (types == "CASH_OUT")) & (rng.random(n) < 0.12)
        # the LEAK: fraud drains the origin account to 0 (Part 5.3 caveat, reproduced)
        new_org = np.where(is_fraud, 0.0, np.maximum(old_org - amount, 0.0))
        df = pd.DataFrame({
            "step": rng.integers(1, 744, n),
            "type": types,
            "amount": amount,
            "nameOrig": [f"C{int(x)}" for x in rng.integers(1, 9999, n)],
            "oldbalanceOrg": old_org,
            "newbalanceOrig": new_org,
            "nameDest": [f"C{int(x)}" for x in rng.integers(1, 9999, n)],
            "oldbalanceDest": rng.gamma(2.0, 20000.0, n).round(2),
            "newbalanceDest": rng.gamma(2.0, 20000.0, n).round(2),
            "isFraud": is_fraud.astype(int),
        })
        return df.sort_values("step").reset_index(drop=True)

    def to_l0(self, df: pd.DataFrame) -> list[L0Event]:
        """Map PaySim rows to L0 transaction events for the streaming scale test."""
        events: list[L0Event] = []
        for _, r in df.iterrows():
            ts = f"2024-01-01T{int(r['step']) % 24:02d}:00:00Z"
            emp = make_id("employee", "paysim", r["nameOrig"])
            events.append(L0Event(
                event_id=make_id("event", "paysim", r["nameOrig"], r["nameDest"], r["step"]),
                ts=ts,
                actor=Actor(employee_id=emp, role="customer"),
                action=Action(verb=str(r["type"]).lower(), channel="upi"),
                object=ObjectRef(
                    account_id=make_id("account", r["nameOrig"]),
                    beneficiary_id=make_id("beneficiary", r["nameDest"]),
                    amount=int(round(float(r["amount"]) * 100)),
                    currency=CURRENCY_DEFAULT,
                ),
                context=Context(ts=ts, layer="application"),
            ))
        return events


def demo() -> pd.DataFrame:
    return PaySimLoader().synthetic()
