"""Autoencoder anomaly detector with per-feature reconstruction explanations (L2; §20.2).

Real path (torch present): a symmetric MLP autoencoder — bottleneck ~1/4-1/2 input dim,
ReLU activations, dropout in [0.1, 0.3], MSE loss, early stopping. Anomaly score =
per-row reconstruction error; the flagging threshold is the 99th percentile of the
training (assumed-normal) reconstruction error.

Fallback (no torch): a PCA-reconstruction autoencoder (sklearn ``PCA``) — project to a
low-rank subspace and reconstruct; the residual is the reconstruction error.

``explain`` overrides the base to emit per-feature reconstruction-error
``ReasonCode(source="shap", feature=<col>, contribution=<err share>)`` for the top_k
worst features (defence-in-depth, cross-checkable against rules + raw evidence).
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ml._optional import HAS_TORCH
from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.config.seeds import GLOBAL_SEED
from ml.layers.l2._common import Standardizer, as_matrix


class AutoEncoderDetector(BaseDetector):
    """MLP autoencoder (torch) with PCA-reconstruction fallback."""

    layer = "L2"

    def __init__(
        self,
        *,
        bottleneck_ratio: float = 0.35,
        dropout: float = 0.2,
        epochs: int = 60,
        batch_size: int = 64,
        lr: float = 1e-3,
        patience: int = 8,
        val_frac: float = 0.2,
        threshold_pct: float = 99.0,
        random_state: int = GLOBAL_SEED,
        name: str = "l2_autoencoder",
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name=name, version=version)
        if not 0.0 < bottleneck_ratio < 1.0:
            raise ValueError("bottleneck_ratio must be in (0, 1)")
        if not 0.1 <= dropout <= 0.3:
            raise ValueError("dropout must be in [0.1, 0.3] per blueprint §20.2")
        self.bottleneck_ratio = bottleneck_ratio
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.patience = patience
        self.val_frac = val_frac
        self.threshold_pct = threshold_pct
        self.random_state = random_state
        self._backend = "torch" if HAS_TORCH else "pca"
        self._scaler = Standardizer()
        self._net: Any = None
        self._pca: Any = None
        self._feature_names: list[str] = []
        self.threshold_: float = 0.0

    # ------------------------------------------------------------------ #
    def fit(self, X: Any, y: Optional[Any] = None) -> "AutoEncoderDetector":
        mat, names = as_matrix(X)
        self._feature_names = names
        Z = self._scaler.fit_transform(mat)
        n_feat = Z.shape[1]
        bottleneck = max(1, int(round(n_feat * self.bottleneck_ratio)))
        if HAS_TORCH:
            self._fit_torch(Z, n_feat, bottleneck)
        else:  # pragma: no cover - sklearn fallback (torch present on reference venv)
            self._fit_pca(Z, bottleneck)
        train_err = self._recon_error(Z)
        self.threshold_ = float(np.percentile(train_err, self.threshold_pct))
        self._fitted = True
        return self

    def _fit_torch(self, Z: np.ndarray, n_feat: int, bottleneck: int) -> None:
        import torch
        from torch import nn

        torch.manual_seed(self.random_state)
        rng = np.random.default_rng(self.random_state)
        hidden = max(bottleneck, n_feat // 2)

        net = nn.Sequential(
            nn.Linear(n_feat, hidden),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(hidden, bottleneck),
            nn.ReLU(),
            nn.Linear(bottleneck, hidden),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(hidden, n_feat),
        )
        n = Z.shape[0]
        idx = rng.permutation(n)
        n_val = max(1, int(n * self.val_frac)) if n > 4 else 0
        val_idx, tr_idx = idx[:n_val], idx[n_val:]
        if tr_idx.size == 0:
            tr_idx = idx
        Xt = torch.tensor(Z, dtype=torch.float32)
        opt = torch.optim.Adam(net.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()
        best_val = float("inf")
        best_state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        bad = 0
        bs = min(self.batch_size, max(1, tr_idx.size))
        for _ in range(self.epochs):
            net.train()
            perm = rng.permutation(tr_idx)
            for s in range(0, perm.size, bs):
                b = perm[s : s + bs]
                xb = Xt[b]
                opt.zero_grad()
                loss = loss_fn(net(xb), xb)
                loss.backward()
                opt.step()
            net.eval()
            with torch.no_grad():
                ref = val_idx if n_val > 0 else tr_idx
                xv = Xt[ref]
                vloss = float(loss_fn(net(xv), xv).item())
            if vloss < best_val - 1e-6:
                best_val = vloss
                best_state = {
                    k: v.detach().clone() for k, v in net.state_dict().items()
                }
                bad = 0
            else:
                bad += 1
                if bad >= self.patience:
                    break
        net.load_state_dict(best_state)
        net.eval()
        self._net = net

    def _fit_pca(self, Z: np.ndarray, bottleneck: int) -> None:  # pragma: no cover
        from sklearn.decomposition import PCA

        n_comp = max(1, min(bottleneck, Z.shape[1], max(1, Z.shape[0] - 1)))
        self._pca = PCA(n_components=n_comp, random_state=self.random_state)
        self._pca.fit(Z)

    # ------------------------------------------------------------------ #
    def _per_feature_error(self, X: Any) -> tuple[np.ndarray, list[str]]:
        mat, names = as_matrix(X)
        Z = self._scaler.transform(mat)
        recon = self._reconstruct(Z)
        return (Z - recon) ** 2, names

    def _reconstruct(self, Z: np.ndarray) -> np.ndarray:
        if HAS_TORCH and self._net is not None:
            import torch

            with torch.no_grad():
                out = self._net(torch.tensor(Z, dtype=torch.float32)).numpy()
            return out
        recon = self._pca.inverse_transform(self._pca.transform(Z))  # pragma: no cover
        return recon  # pragma: no cover

    def _recon_error(self, Z: np.ndarray) -> np.ndarray:
        recon = self._reconstruct(Z)
        return ((Z - recon) ** 2).mean(axis=1)

    def score_samples(self, X: Any) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("AutoEncoderDetector must be fit before scoring")
        per_feat, _ = self._per_feature_error(X)
        err = per_feat.mean(axis=1)
        return normalize_scores(err, method="rank")

    def is_anomaly(self, X: Any) -> np.ndarray:
        """Boolean flag: reconstruction error exceeds the 99th-pctile training threshold."""
        mat, _ = as_matrix(X)
        Z = self._scaler.transform(mat)
        return self._recon_error(Z) > self.threshold_

    def explain(self, X: Any, top_k: int = 5) -> list[list[ReasonCode]]:
        """Per-feature reconstruction-error reason codes for the top_k worst features."""
        per_feat, names = self._per_feature_error(X)
        reasons: list[list[ReasonCode]] = []
        for row in per_feat:
            total = float(row.sum()) or 1.0
            order = np.argsort(row)[::-1][:top_k]
            rcs = [
                ReasonCode(
                    source="shap",
                    feature=names[j],
                    detail="autoencoder reconstruction error",
                    contribution=float(row[j] / total),
                )
                for j in order
                if row[j] > 0
            ]
            reasons.append(rcs)
        return reasons
