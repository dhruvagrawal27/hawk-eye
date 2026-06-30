"""Anomaly Transformer (ML-5): compact attention + reconstruction detector.

Xu et al. 2022. The key idea is *association discrepancy*: anomalies struggle to
build series-wide associations, so their attention concentrates locally. We keep a
compact version: a small transformer reconstructs the window, and the per-window
anomaly score combines reconstruction error with the locality (entropy) of its
attention map. Compact (1 layer, tiny dim, few epochs).

torch import lives inside the methods; ``fit`` raises ``require('torch')`` if absent.
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


class AnomalyTransformer(BaseDetector):
    """Compact attention+reconstruction detector with association-discrepancy scoring."""

    layer = "L4"

    def __init__(self, d_model: int = 16, window: int = 20, epochs: int = 10,
                 version: str = "0.1.0") -> None:
        super().__init__(name="l4_anomaly_transformer", version=version)
        self.d_model = int(d_model)
        self.window = int(window)
        self.epochs = int(epochs)
        self._model = None
        self._c = 0

    def _build(self):
        import torch
        from torch import nn

        d_model, c, w = self.d_model, self._c, self.window

        class _AT(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.inp = nn.Linear(c, d_model)
                self.attn = nn.MultiheadAttention(d_model, num_heads=2,
                                                  batch_first=True, dropout=0.0)
                self.out = nn.Linear(d_model, c)

            def forward(self, x):
                h = self.inp(x)
                a, w_attn = self.attn(h, h, h, need_weights=True,
                                      average_attn_weights=True)
                recon = self.out(a)
                return recon, w_attn  # w_attn: (n, w, w)

        return _AT()

    def fit(self, X, y=None) -> "AnomalyTransformer":
        if not HAS_TORCH:
            require("torch", reason="AnomalyTransformer needs torch")
        import torch

        X3 = _win3(X, self.window)
        if X3.shape[0] == 0:
            self._fitted = True
            return self
        self._c = X3.shape[2]
        self.window = X3.shape[1]
        self._mu = X3.mean(axis=(0, 1), keepdims=True)
        self._sd = X3.std(axis=(0, 1), keepdims=True) + 1e-6
        Xn = (X3 - self._mu) / self._sd
        torch.manual_seed(1405)
        t = torch.tensor(Xn, dtype=torch.float32)
        model = self._build()
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        mse = torch.nn.MSELoss()
        model.train()
        for _ in range(self.epochs):
            recon, _ = model(t)
            loss = mse(recon, t)
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
            recon, w_attn = self._model(t)
            recon_err = ((t - recon) ** 2).mean(dim=(1, 2)).numpy()
            # association discrepancy proxy: low attention entropy = concentrated =
            # anomalous. entropy over each row of the attention map, averaged.
            p = torch.clamp(w_attn, 1e-9, 1.0)
            ent = -(p * torch.log(p)).sum(dim=-1).mean(dim=1).numpy()  # (n,)
        # high recon error OR low entropy (concentrated attention) -> anomalous
        disc = normalize_scores(-ent, method="minmax")
        rec = normalize_scores(recon_err, method="minmax")
        return normalize_scores(0.5 * rec + 0.5 * disc, method="minmax")


__all__ = ["AnomalyTransformer"]
