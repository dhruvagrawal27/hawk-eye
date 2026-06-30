"""L4 simple baselines (ML-5) — THESE RUN FIRST (blueprint §20.4, §22.2).

The non-negotiable L4 rule: run cheap, well-understood baselines over windowed
event streams *before* any deep model, and keep a deep model only if it beats these
under honest (non-point-adjust) evaluation (see ``gate.keep_if_beats_baselines``).

Baselines (all ``BaseDetector`` -> ``score_samples`` in [0,1]):
* ``WindowedPCADetector``         — reconstruction error from a low-rank PCA of windows.
* ``WindowedIsolationForestDetector`` — IsolationForest over flattened windows.
* ``MatrixProfileDetector``       — matrix-profile-style nearest-neighbour distance
  one-liner (each window's distance to its closest *other* window).
* ``ConvAutoencoderBaseline``     — tiny conv/MLP autoencoder (torch when present;
  clean PCA-reconstruction fallback otherwise).

Heavy imports (torch) live INSIDE methods so the module always imports.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from ml._optional import HAS_TORCH
from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.layers.l4.windows import WindowSet


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _as_flat(X) -> np.ndarray:
    """Accept a WindowSet or a 2-/3-D array and return a 2-D flat matrix."""
    if isinstance(X, WindowSet):
        return X.flat.astype(np.float64)
    arr = np.asarray(X, dtype=np.float64)
    if arr.ndim == 3:
        return arr.reshape(arr.shape[0], -1)
    if arr.ndim == 1:
        return arr.reshape(-1, 1)
    return arr


def _per_feature_recon_error(X3: np.ndarray, R3: np.ndarray) -> np.ndarray:
    """Mean squared recon error per feature channel, averaged over time."""
    # X3,R3: (n, window, n_feat) -> (n_feat,)
    err = (X3 - R3) ** 2
    return err.mean(axis=(0, 1))


class _WindowedBase(BaseDetector):
    """Shared machinery: keep the last fitted WindowSet for explanations."""

    layer = "L4"

    def __init__(self, name: str, version: str = "0.1.0", window: int = 20) -> None:
        super().__init__(name=name, version=version)
        self.window = int(window)
        self._feature_names: list[str] = []
        self._n_feat: int = 0

    def _coerce(self, X) -> tuple[np.ndarray, Optional[WindowSet]]:
        if isinstance(X, WindowSet):
            self._feature_names = X.feature_names or self._feature_names
            self._n_feat = X.X.shape[2] if X.X.ndim == 3 else self._n_feat
            return X.flat.astype(np.float64), X
        return _as_flat(X), None


# --------------------------------------------------------------------------- #
# 1. Windowed PCA reconstruction                                              #
# --------------------------------------------------------------------------- #
class WindowedPCADetector(_WindowedBase):
    """PCA over flattened windows; anomaly = reconstruction error (blueprint §20.4)."""

    def __init__(
        self, n_components: int = 8, window: int = 20, version: str = "0.1.0"
    ) -> None:
        super().__init__(name="l4_windowed_pca", version=version, window=window)
        self.n_components = int(n_components)
        self._pca: Any = None

    def fit(self, X, y=None) -> "WindowedPCADetector":
        from sklearn.decomposition import PCA

        flat, _ = self._coerce(X)
        if flat.shape[0] == 0:
            self._fitted = True
            return self
        k = max(
            1,
            min(
                self.n_components,
                flat.shape[1],
                flat.shape[0] - 1 if flat.shape[0] > 1 else 1,
            ),
        )
        self._pca = PCA(n_components=k, random_state=1405)
        self._pca.fit(flat)
        self._fitted = True
        return self

    def _recon_err(self, flat: np.ndarray) -> np.ndarray:
        if self._pca is None or flat.shape[0] == 0:
            return np.zeros(flat.shape[0])
        recon = self._pca.inverse_transform(self._pca.transform(flat))
        return ((flat - recon) ** 2).mean(axis=1)

    def score_samples(self, X) -> np.ndarray:
        flat, _ = self._coerce(X)
        return normalize_scores(self._recon_err(flat), method="minmax")

    def explain(self, X, top_k: int = 3) -> list[list[ReasonCode]]:
        flat, ws = self._coerce(X)
        if ws is None or self._pca is None or flat.shape[0] == 0:
            return [[] for _ in range(flat.shape[0])]
        recon = self._pca.inverse_transform(self._pca.transform(flat))
        n_feat = ws.X.shape[2]
        per = (
            ((flat - recon) ** 2)
            .reshape(flat.shape[0], self.window, n_feat)
            .mean(axis=1)
        )
        names = ws.feature_names or [f"f{i}" for i in range(n_feat)]
        out: list[list[ReasonCode]] = []
        for row in per:
            idx = np.argsort(-row)[:top_k]
            out.append(
                [
                    ReasonCode(
                        source="attention",
                        feature=names[i],
                        detail="window reconstruction error",
                        contribution=float(row[i]),
                    )
                    for i in idx
                    if row[i] > 0
                ]
            )
        return out


# --------------------------------------------------------------------------- #
# 2. Windowed IsolationForest                                                  #
# --------------------------------------------------------------------------- #
class WindowedIsolationForestDetector(_WindowedBase):
    """IsolationForest over flattened windows (blueprint §20.2/§20.4 params)."""

    def __init__(
        self, n_estimators: int = 150, window: int = 20, version: str = "0.1.0"
    ) -> None:
        super().__init__(name="l4_windowed_iforest", version=version, window=window)
        self.n_estimators = int(n_estimators)
        self._if: Any = None

    def fit(self, X, y=None) -> "WindowedIsolationForestDetector":
        from sklearn.ensemble import IsolationForest

        flat, _ = self._coerce(X)
        if flat.shape[0] == 0:
            self._fitted = True
            return self
        self._if = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=min(256, flat.shape[0]),
            max_features=1.0,
            contamination="auto",
            random_state=1405,
        )
        self._if.fit(flat)
        self._fitted = True
        return self

    def score_samples(self, X) -> np.ndarray:
        flat, _ = self._coerce(X)
        if self._if is None or flat.shape[0] == 0:
            return np.zeros(flat.shape[0])
        # IsolationForest: higher decision_function = more normal -> negate.
        raw = -self._if.decision_function(flat)
        return normalize_scores(raw, method="minmax")


# --------------------------------------------------------------------------- #
# 3. Matrix-profile-style nearest-neighbour distance (one-liner baseline)     #
# --------------------------------------------------------------------------- #
class MatrixProfileDetector(_WindowedBase):
    """Matrix-profile-style baseline: each window's distance to its nearest *other*
    window. Discords (large NN distance) are anomalous. No external deps."""

    def __init__(self, window: int = 20, version: str = "0.1.0") -> None:
        super().__init__(name="l4_matrix_profile", version=version, window=window)
        self._train: Optional[np.ndarray] = None

    def fit(self, X, y=None) -> "MatrixProfileDetector":
        flat, _ = self._coerce(X)
        # z-normalise columns so scale-free (matrix-profile convention).
        mu = flat.mean(axis=0, keepdims=True)
        sd = flat.std(axis=0, keepdims=True) + 1e-9
        self._mu, self._sd = mu, sd
        self._train = (flat - mu) / sd if flat.shape[0] else flat
        self._fitted = True
        return self

    def score_samples(self, X) -> np.ndarray:
        flat, _ = self._coerce(X)
        if self._train is None or self._train.shape[0] == 0 or flat.shape[0] == 0:
            return np.zeros(flat.shape[0])
        q = (flat - self._mu) / self._sd
        # nearest-neighbour distance to the training set (the matrix-profile value).
        # (n_q, n_train) pairwise — fine for the small windowed sets L4 handles.
        d = np.sqrt(((q[:, None, :] - self._train[None, :, :]) ** 2).sum(axis=2))
        same = (
            np.allclose(q.shape, self._train.shape)
            and q.shape[0] == self._train.shape[0]
        )
        if same and np.allclose(q, self._train):
            np.fill_diagonal(d, np.inf)  # exclude self-match (the trivial discord rule)
        nn = d.min(axis=1)
        nn[~np.isfinite(nn)] = 0.0
        return normalize_scores(nn, method="minmax")


# --------------------------------------------------------------------------- #
# 4. Tiny conv/MLP autoencoder baseline (torch when present)                   #
# --------------------------------------------------------------------------- #
class ConvAutoencoderBaseline(_WindowedBase):
    """Small autoencoder over windows. Uses a tiny 1-D conv AE under torch; falls back
    to a PCA-reconstruction surrogate when torch is absent (module still imports)."""

    def __init__(
        self,
        latent_dim: int = 8,
        window: int = 20,
        epochs: int = 8,
        version: str = "0.1.0",
    ) -> None:
        super().__init__(name="l4_conv_ae", version=version, window=window)
        self.latent_dim = int(latent_dim)
        self.epochs = int(epochs)
        self._model: Any = None
        self._fallback: Optional[WindowedPCADetector] = None

    def fit(self, X, y=None) -> "ConvAutoencoderBaseline":
        flat, ws = self._coerce(X)
        if not HAS_TORCH:
            self._fallback = WindowedPCADetector(
                n_components=self.latent_dim, window=self.window
            )
            self._fallback.fit(X)
            self._fitted = True
            return self
        import torch
        from torch import nn

        if ws is None:
            n_feat = max(1, flat.shape[1] // self.window)
            X3 = flat.reshape(flat.shape[0], self.window, n_feat)
        else:
            X3 = ws.X
        n, w, c = X3.shape
        self._n_feat = c
        torch.manual_seed(1405)
        # (n, c, w) for conv1d
        t = torch.tensor(X3, dtype=torch.float32).transpose(1, 2)
        hidden = max(4, self.latent_dim)

        class _AE(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.enc = nn.Sequential(nn.Conv1d(c, hidden, 3, padding=1), nn.ReLU())
                self.dec = nn.Sequential(nn.Conv1d(hidden, c, 3, padding=1))

            def forward(self, x):
                return self.dec(self.enc(x))

        model = _AE()
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        lossf = nn.MSELoss()
        model.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            out = model(t)
            loss = lossf(out, t)
            loss.backward()
            opt.step()
        model.eval()
        self._model = model
        self._fitted = True
        return self

    def score_samples(self, X) -> np.ndarray:
        if self._fallback is not None:
            return self._fallback.score_samples(X)
        flat, ws = self._coerce(X)
        if self._model is None or flat.shape[0] == 0:
            return np.zeros(flat.shape[0])
        import torch

        c = self._n_feat or (ws.X.shape[2] if ws is not None else 1)
        X3 = ws.X if ws is not None else flat.reshape(flat.shape[0], self.window, c)
        with torch.no_grad():
            t = torch.tensor(X3, dtype=torch.float32).transpose(1, 2)
            out = self._model(t).transpose(1, 2).numpy()
        err = ((X3 - out) ** 2).mean(axis=(1, 2))
        return normalize_scores(err, method="minmax")


def all_baselines(window: int = 20) -> dict[str, BaseDetector]:
    """The L4 baseline suite, in run order (cheap -> tiny-deep)."""
    return {
        "windowed_pca": WindowedPCADetector(window=window),
        "windowed_iforest": WindowedIsolationForestDetector(window=window),
        "matrix_profile": MatrixProfileDetector(window=window),
        "conv_ae": ConvAutoencoderBaseline(window=window, epochs=8),
    }


def run_baselines_first(ws: WindowSet, window: int = 20) -> dict[str, np.ndarray]:
    """Fit + score every baseline on a WindowSet. Returns name -> [0,1] scores.

    This is the function the L4 pipeline calls BEFORE any deep model.
    """
    out: dict[str, np.ndarray] = {}
    for name, det in all_baselines(window=window).items():
        det.fit(ws)
        out[name] = det.score_samples(ws)
    return out


__all__ = [
    "WindowedPCADetector",
    "WindowedIsolationForestDetector",
    "MatrixProfileDetector",
    "ConvAutoencoderBaseline",
    "all_baselines",
    "run_baselines_first",
]
