"""USAD (ML-5): UnSupervised Anomaly Detection with two adversarially-trained AEs.

Audibert et al. 2020. A shared encoder feeds two decoders (AE1, AE2). AE2 is trained
to discriminate AE1's reconstructions (adversarial), while AE1 tries to fool it. At
inference the anomaly score blends both reconstruction terms.

Compact build: tiny MLP over flattened windows, small latent dim, few epochs.
torch import lives inside ``fit``/``score_samples`` so the module always imports; if
torch is missing, ``fit`` raises a clear ``require('torch')``.
"""

from __future__ import annotations

import numpy as np

from ml._optional import HAS_TORCH, require
from ml.base import BaseDetector, normalize_scores
from ml.layers.l4.windows import WindowSet


def _flat(X) -> np.ndarray:
    if isinstance(X, WindowSet):
        return X.flat.astype(np.float32)
    arr = np.asarray(X, dtype=np.float32)
    if arr.ndim == 3:
        return arr.reshape(arr.shape[0], -1)
    return arr


class USAD(BaseDetector):
    """Two-autoencoder adversarial detector (window ~10-100 steps, small latent)."""

    layer = "L4"

    def __init__(
        self,
        latent_dim: int = 8,
        epochs: int = 12,
        alpha: float = 0.5,
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name="l4_usad", version=version)
        self.latent_dim = int(latent_dim)
        self.epochs = int(epochs)
        self.alpha = float(alpha)  # blend weight at inference
        self._model = None
        self._dim = 0
        self._mu = None
        self._sd = None

    def _build(self):
        from torch import nn

        d, h = self._dim, max(2, self.latent_dim)

        class _USADNet(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.enc = nn.Sequential(
                    nn.Linear(d, max(8, d // 2)),
                    nn.ReLU(),
                    nn.Linear(max(8, d // 2), h),
                    nn.ReLU(),
                )
                self.dec1 = nn.Sequential(
                    nn.Linear(h, max(8, d // 2)),
                    nn.ReLU(),
                    nn.Linear(max(8, d // 2), d),
                )
                self.dec2 = nn.Sequential(
                    nn.Linear(h, max(8, d // 2)),
                    nn.ReLU(),
                    nn.Linear(max(8, d // 2), d),
                )

            def forward(self, x):
                z = self.enc(x)
                w1 = self.dec1(z)
                w2 = self.dec2(z)
                w3 = self.dec2(self.enc(w1))  # AE2 reconstructs AE1's output
                return w1, w2, w3

        return _USADNet()

    def fit(self, X, y=None) -> "USAD":
        if not HAS_TORCH:
            require("torch", reason="USAD adversarial autoencoder needs torch")
        import torch

        flat = _flat(X)
        if flat.shape[0] == 0:
            self._fitted = True
            return self
        self._dim = flat.shape[1]
        self._mu = flat.mean(axis=0, keepdims=True)
        self._sd = flat.std(axis=0, keepdims=True) + 1e-6
        Xn = (flat - self._mu) / self._sd
        torch.manual_seed(1405)
        t = torch.tensor(Xn, dtype=torch.float32)
        model = self._build()
        opt1 = torch.optim.Adam(
            list(model.enc.parameters()) + list(model.dec1.parameters()), lr=1e-2
        )
        opt2 = torch.optim.Adam(
            list(model.enc.parameters()) + list(model.dec2.parameters()), lr=1e-2
        )
        mse = torch.nn.MSELoss()
        model.train()
        for ep in range(1, self.epochs + 1):
            n = float(ep)
            w1, w2, w3 = model(t)
            # AE1: minimise its own recon + fool AE2 (make w3 ~ input)
            loss1 = (1.0 / n) * mse(w1, t) + (1.0 - 1.0 / n) * mse(w3, t)
            opt1.zero_grad()
            loss1.backward()
            opt1.step()
            w1, w2, w3 = model(t)
            # AE2: minimise own recon - distinguish AE1 reconstructions
            loss2 = (1.0 / n) * mse(w2, t) - (1.0 - 1.0 / n) * mse(w3, t)
            opt2.zero_grad()
            loss2.backward()
            opt2.step()
        model.eval()
        self._model = model
        self._fitted = True
        return self

    def score_samples(self, X) -> np.ndarray:
        flat = _flat(X)
        if self._model is None or flat.shape[0] == 0:
            return np.zeros(flat.shape[0])
        import torch

        Xn = (flat - self._mu) / self._sd
        with torch.no_grad():
            t = torch.tensor(Xn, dtype=torch.float32)
            w1, w2, w3 = self._model(t)
            # USAD score: alpha*||x-w1|| + (1-alpha)*||x-w3||
            s1 = ((t - w1) ** 2).mean(dim=1).numpy()
            s3 = ((t - w3) ** 2).mean(dim=1).numpy()
        raw = self.alpha * s1 + (1.0 - self.alpha) * s3
        return normalize_scores(raw, method="minmax")


__all__ = ["USAD"]
