"""Transfer learning: pretrain on CERT/Elliptic, fine-tune on own data (ML-8; Part 5.5).

Pretrain a feature encoder on a public corpus (CERT insider / Elliptic graph), then
fine-tune on our (small) labeled target. torch autoencoder pretraining when available;
a PCA-encoder fallback otherwise. Public-data results are a sanity check, never a
production-performance claim (Part 5.3).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from ml._optional import optional_import
from ml.config.seeds import GLOBAL_SEED, seed_everything


class TransferEncoder:
    """Encoder pretrained on a source corpus, fine-tuned with a head on the target."""

    def __init__(self, emb_dim: int = 16, hidden: int = 32, seed: int = GLOBAL_SEED) -> None:
        self.emb_dim = emb_dim
        self.hidden = hidden
        self.seed = seed
        self._scaler = StandardScaler()
        self._torch_ae = None  # (encoder, decoder) when torch is used
        self._pca = None       # sklearn PCA when torch absent
        self._head: Optional[LogisticRegression] = None
        self._backend = "pca"

    # ----- pretrain (unsupervised reconstruction on the source corpus) ----- #
    def pretrain(self, X_source, epochs: int = 30) -> "TransferEncoder":
        seed_everything(self.seed)
        Xs = self._scaler.fit_transform(np.asarray(X_source, dtype=float))
        torch = optional_import("torch")
        if torch is not None:
            self._backend = "torch"
            self._pretrain_torch(torch, Xs, epochs)
        else:  # pragma: no cover - torch present in reference env
            from sklearn.decomposition import PCA

            self._backend = "pca"
            self._pca = PCA(n_components=min(self.emb_dim, Xs.shape[1]), random_state=self.seed).fit(Xs)
        return self

    def _pretrain_torch(self, torch, Xs: np.ndarray, epochs: int) -> None:
        nn = torch.nn
        in_dim = Xs.shape[1]
        enc = nn.Sequential(nn.Linear(in_dim, self.hidden), nn.ReLU(), nn.Linear(self.hidden, self.emb_dim))
        dec = nn.Sequential(nn.Linear(self.emb_dim, self.hidden), nn.ReLU(), nn.Linear(self.hidden, in_dim))
        params = list(enc.parameters()) + list(dec.parameters())
        opt = torch.optim.Adam(params, lr=1e-2)
        loss_fn = nn.MSELoss()
        xt = torch.tensor(Xs, dtype=torch.float32)
        enc.train(); dec.train()
        for _ in range(epochs):
            opt.zero_grad()
            recon = dec(enc(xt))
            loss = loss_fn(recon, xt)
            loss.backward()
            opt.step()
        enc.eval()
        self._torch_ae = (enc, dec)

    # ----- embed / finetune ----- #
    def embed(self, X) -> np.ndarray:
        Xs = self._scaler.transform(np.asarray(X, dtype=float))
        if self._backend == "torch" and self._torch_ae is not None:
            torch = optional_import("torch")
            enc = self._torch_ae[0]
            with torch.no_grad():
                return enc(torch.tensor(Xs, dtype=torch.float32)).numpy()
        return self._pca.transform(Xs)

    def finetune(self, X_target, y_target) -> "TransferEncoder":
        emb = self.embed(X_target)
        self._head = LogisticRegression(max_iter=500, class_weight="balanced")
        self._head.fit(emb, np.asarray(y_target).astype(int).ravel())
        return self

    def predict_proba(self, X) -> np.ndarray:
        if self._head is None:
            raise RuntimeError("call finetune() before predict_proba()")
        return self._head.predict_proba(self.embed(X))[:, 1]


def from_scratch_baseline(X_target, y_target, seed: int = GLOBAL_SEED):
    """A no-transfer baseline (logistic on raw standardized features) for comparison."""
    scaler = StandardScaler()
    head = LogisticRegression(max_iter=500, class_weight="balanced")
    head.fit(scaler.fit_transform(np.asarray(X_target, dtype=float)), np.asarray(y_target).astype(int).ravel())

    def predict_proba(X):
        return head.predict_proba(scaler.transform(np.asarray(X, dtype=float)))[:, 1]

    return predict_proba


def load_public_source(name: str = "cert", n: int = 600) -> Optional[pd.DataFrame]:
    """Load a numeric source feature matrix from DATA's public loaders (synthetic fallback).

    Returns None if the loader is unavailable. # STUB: real CERT/Elliptic files land via DATA.
    """
    try:  # pragma: no cover - depends on DATA package being importable
        import sys, os

        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if root not in sys.path:
            sys.path.insert(0, root)
        if name == "cert":
            from data.datasets.loaders.cert import CertLoader  # type: ignore
            from ml.adapters.featurize import event_level_features

            events, _ = CertLoader().synthetic()
            df = events if isinstance(events, pd.DataFrame) else pd.DataFrame(events)
            return event_level_features(df).select_dtypes("number")
        if name == "elliptic":
            from data.datasets.loaders.elliptic import EllipticLoader  # type: ignore

            g = EllipticLoader().synthetic() if hasattr(EllipticLoader(), "synthetic") else EllipticLoader().load("")
            nodes = g["nodes"]
            return nodes.select_dtypes("number")
    except Exception:
        return None
    return None
