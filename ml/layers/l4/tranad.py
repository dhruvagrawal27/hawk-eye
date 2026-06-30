"""TranAD (ML-5): transformer with focus-score self-conditioning + adversarial recon.

Tuli et al. 2022. A transformer encoder reconstructs a window twice: phase 1 produces
a coarse reconstruction, whose error becomes a *focus score* that conditions phase 2.
Two decoders are trained adversarially (one minimises recon, the other amplifies it),
mirroring USAD inside a transformer.

Compact build: 1 encoder layer, tiny model dim, few epochs over windowed features.
torch import is inside the methods; ``fit`` raises ``require('torch')`` if absent.
"""
from __future__ import annotations

import numpy as np

from ml._optional import HAS_TORCH, require
from ml.base import BaseDetector, normalize_scores
from ml.layers.l4.windows import WindowSet


def _win3(X, window: int) -> np.ndarray:
    if isinstance(X, WindowSet):
        return X.X.astype(np.float32)
    arr = np.asarray(X, dtype=np.float32)
    if arr.ndim == 3:
        return arr
    n_feat = max(1, arr.shape[1] // window)
    return arr.reshape(arr.shape[0], window, n_feat)


class TranAD(BaseDetector):
    """Transformer focus-score + adversarial reconstruction detector (compact)."""

    layer = "L4"

    def __init__(self, d_model: int = 16, window: int = 20, epochs: int = 10,
                 version: str = "0.1.0") -> None:
        super().__init__(name="l4_tranad", version=version)
        self.d_model = int(d_model)
        self.window = int(window)
        self.epochs = int(epochs)
        self._model = None
        self._c = 0

    def _build(self):
        import torch
        from torch import nn

        d_model, c = self.d_model, self._c

        class _TranAD(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.inp = nn.Linear(c, d_model)
                enc = nn.TransformerEncoderLayer(d_model=d_model, nhead=2,
                                                 dim_feedforward=2 * d_model,
                                                 batch_first=True, dropout=0.0)
                self.encoder = nn.TransformerEncoder(enc, num_layers=1)
                self.dec1 = nn.Linear(d_model, c)
                self.dec2 = nn.Linear(d_model, c)

            def _enc(self, x_feat):
                # x_feat: (n, w, c) concatenated with focus -> here focus added to input
                h = self.inp(x_feat)
                return self.encoder(h)

            def forward(self, x, focus):
                # phase 1: no focus (zeros)
                h1 = self._enc(x * (1.0 + 0.0 * focus))
                o1 = self.dec1(h1)
                # phase 2: condition on focus score (elementwise scale)
                h2 = self._enc(x * (1.0 + focus))
                o2 = self.dec2(h2)
                return o1, o2

        return _TranAD()

    def fit(self, X, y=None) -> "TranAD":
        if not HAS_TORCH:
            require("torch", reason="TranAD transformer needs torch")
        import torch

        X3 = _win3(X, self.window)
        if X3.shape[0] == 0:
            self._fitted = True
            return self
        self._c = X3.shape[2]
        self._mu = X3.mean(axis=(0, 1), keepdims=True)
        self._sd = X3.std(axis=(0, 1), keepdims=True) + 1e-6
        Xn = (X3 - self._mu) / self._sd
        torch.manual_seed(1405)
        t = torch.tensor(Xn, dtype=torch.float32)
        model = self._build()
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        mse = torch.nn.MSELoss()
        model.train()
        for ep in range(1, self.epochs + 1):
            n = float(ep)
            focus = torch.zeros_like(t)
            o1, o2 = model(t, focus)
            # focus score = phase-1 recon error, fed back (self-conditioning)
            focus = ((t - o1) ** 2).detach()
            o1, o2 = model(t, focus)
            l1 = (1.0 / n) * mse(o1, t) + (1.0 - 1.0 / n) * mse(o2, t)
            l2 = (1.0 / n) * mse(o2, t) - (1.0 - 1.0 / n) * mse(o2, t)
            loss = l1 + l2
            opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        self._model = model
        self._fitted = True
        return self

    def score_samples(self, X) -> np.ndarray:
        X3 = _win3(X, self.window)
        if self._model is None or X3.shape[0] == 0:
            return np.zeros(X3.shape[0])
        import torch

        Xn = (X3 - self._mu) / self._sd
        with torch.no_grad():
            t = torch.tensor(Xn, dtype=torch.float32)
            focus = torch.zeros_like(t)
            o1, _ = self._model(t, focus)
            focus = ((t - o1) ** 2)
            o1, o2 = self._model(t, focus)
            # blend the two phase reconstruction errors (the TranAD anomaly score)
            err = (0.5 * ((t - o1) ** 2) + 0.5 * ((t - o2) ** 2)).mean(dim=(1, 2)).numpy()
        return normalize_scores(err, method="minmax")


__all__ = ["TranAD"]
