"""LAXCAT (ML-5): explainable supervised CNN + variable-attention + temporal-attention.

Hsieh et al. 2021 ("Explainable Multivariate Time Series Classification"). A 1-D CNN
extracts per-variable temporal features; a VARIABLE-attention head says *which features*
drive the classification, and a TEMPORAL-attention head says *which time intervals*.
LAXCAT is an EXPLAINER for flagged sessions — it needs labels (supervised) and is not a
cold-start detector.

Reason codes it emits answer "which variables and which time intervals":
``ReasonCode(source="attention", feature=<var>, detail=<time interval>, contribution=<weight>)``.

torch import lives inside the methods; ``fit`` raises ``require('torch')`` if absent.
Subclasses ``BaseScorer`` (supervised -> predict_proba in [0,1]).
"""
from __future__ import annotations

import numpy as np

from ml._optional import HAS_TORCH, require
from ml.base import BaseScorer, ReasonCode
from ml.layers.l4.windows import WindowSet


def _win3(X, window: int) -> tuple[np.ndarray, list[str]]:
    if isinstance(X, WindowSet):
        return X.X.astype(np.float32), (X.feature_names or
                                        [f"f{i}" for i in range(X.X.shape[2])])
    arr = np.asarray(X, dtype=np.float32)
    if arr.ndim == 3:
        return arr, [f"f{i}" for i in range(arr.shape[2])]
    n_feat = max(1, arr.shape[1] // window)
    a = arr.reshape(arr.shape[0], window, n_feat)
    return a, [f"f{i}" for i in range(n_feat)]


class LAXCAT(BaseScorer):
    """Supervised explainable classifier with variable + temporal attention."""

    layer = "L4"

    def __init__(self, n_intervals: int = 4, conv_channels: int = 8, window: int = 20,
                 epochs: int = 25, version: str = "0.1.0") -> None:
        super().__init__(name="l4_laxcat", version=version)
        self.n_intervals = int(n_intervals)
        self.conv_channels = int(conv_channels)
        self.window = int(window)
        self.epochs = int(epochs)
        self._model = None
        self._c = 0
        self._feature_names: list[str] = []

    def _build(self):
        import torch
        from torch import nn

        c, k, w, n_int = self._c, self.conv_channels, self.window, self.n_intervals
        # intervals partition the window; pool length per interval
        int_len = max(1, w // n_int)

        class _LAXCAT(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                # per-variable temporal conv (depthwise-ish: shared small conv per var)
                self.conv = nn.Conv1d(c, c * k, kernel_size=3, padding=1, groups=c)
                self.var_att = nn.Linear(k, 1)       # variable attention
                self.tmp_att = nn.Linear(c * k, 1)   # temporal-interval attention
                self.int_len = int_len
                self.n_int = n_int
                self.k = k
                self.c = c
                self.clf = nn.Linear(c, 1)

            def forward(self, x):
                # x: (n, w, c) -> conv over time
                h = self.conv(x.transpose(1, 2))           # (n, c*k, w)
                n = h.shape[0]
                h = h.view(n, self.c, self.k, -1)          # (n, c, k, w)
                # ---- temporal attention over intervals ----
                wlen = h.shape[-1]
                il = max(1, wlen // self.n_int)
                # mean-pool each interval -> (n, c, k, n_int)
                pooled = []
                for t in range(self.n_int):
                    seg = h[..., t * il:(t + 1) * il if t < self.n_int - 1 else wlen]
                    pooled.append(seg.mean(dim=-1))
                pooled = torch.stack(pooled, dim=-1)        # (n, c, k, n_int)
                # temporal weights from the flattened (c*k) feature per interval
                tflat = pooled.permute(0, 3, 1, 2).reshape(n, self.n_int, self.c * self.k)
                t_logits = self.tmp_att(tflat).squeeze(-1)  # (n, n_int)
                t_w = torch.softmax(t_logits, dim=1)        # temporal attention
                # weighted sum over intervals -> (n, c, k)
                ctx = (pooled * t_w[:, None, None, :]).sum(dim=-1)
                # ---- variable attention ----
                v_logits = self.var_att(ctx).squeeze(-1)    # (n, c)
                v_w = torch.softmax(v_logits, dim=1)        # variable attention
                feat = (ctx.mean(dim=-1) * v_w)             # (n, c)
                logit = self.clf(feat).squeeze(-1)          # (n,)
                return logit, v_w, t_w

        return _LAXCAT()

    def fit(self, X, y) -> "LAXCAT":
        if not HAS_TORCH:
            require("torch", reason="LAXCAT supervised attention classifier needs torch")
        import torch

        X3, names = _win3(X, self.window)
        self._feature_names = names
        yv = np.asarray(y).astype(np.float32).ravel()
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
        yt = torch.tensor(yv, dtype=torch.float32)
        model = self._build()
        opt = torch.optim.Adam(model.parameters(), lr=5e-3)
        # class imbalance: weight positives (blueprint §5.5)
        pos = float(yv.sum())
        neg = float(len(yv) - pos)
        pos_weight = torch.tensor([neg / pos if pos > 0 else 1.0])
        lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        model.train()
        for _ in range(self.epochs):
            logit, _, _ = model(t)
            loss = lossf(logit, yt)
            opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        self._model = model
        self._fitted = True
        return self

    def _forward(self, X):
        import torch

        X3, _ = _win3(X, self.window)
        if self._model is None or X3.shape[0] == 0:
            return None, None, None, X3
        Xn = (X3 - self._mu) / self._sd
        with torch.no_grad():
            logit, v_w, t_w = self._model(torch.tensor(Xn, dtype=torch.float32))
        return logit.numpy(), v_w.numpy(), t_w.numpy(), X3

    def predict_proba(self, X) -> np.ndarray:
        logit, _, _, X3 = self._forward(X)
        if logit is None:
            return np.full(X3.shape[0], 0.0)
        return 1.0 / (1.0 + np.exp(-logit))

    def reason_codes(self, X, top_k: int = 3) -> list[list[ReasonCode]]:
        logit, v_w, t_w, X3 = self._forward(X)
        n = X3.shape[0]
        if logit is None:
            return [[] for _ in range(n)]
        names = self._feature_names or [f"f{i}" for i in range(X3.shape[2])]
        n_int = t_w.shape[1]
        w = self.window
        il = max(1, w // n_int)
        out: list[list[ReasonCode]] = []
        for r in range(n):
            # dominant time interval
            ti = int(np.argmax(t_w[r]))
            lo = ti * il
            hi = (ti + 1) * il if ti < n_int - 1 else w
            interval = f"steps[{lo}:{hi}] (interval {ti + 1}/{n_int})"
            # top variables by variable-attention
            top_vars = np.argsort(-v_w[r])[:top_k]
            rcs = []
            for vi in top_vars:
                rcs.append(ReasonCode(
                    source="attention",
                    feature=names[vi] if vi < len(names) else f"f{vi}",
                    detail=interval,
                    contribution=float(v_w[r, vi] * t_w[r, ti]),
                ))
            out.append(rcs)
        return out


__all__ = ["LAXCAT"]
