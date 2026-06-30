"""DeepLog (ML-5): next-event LSTM over the verb sequence per session.

Du et al. 2017. Treat each session's ordered verb stream as a "log key" sequence and
learn an LSTM language model of the next verb. A step is anomalous when the *actual*
next verb has low predicted probability (not in the model's top-k); a session's score
aggregates its surprisal. Includes a numpy n-gram fallback so the module works (and is
honest) even without torch.

torch import lives inside ``fit``/``score_samples``; the n-gram path is pure numpy.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

import numpy as np

from ml._optional import HAS_TORCH
from ml.base import BaseDetector, ReasonCode, normalize_scores
from ml.layers.l4.windows import build_verb_sequences


class DeepLog(BaseDetector):
    """Next-event sequence model. score = mean surprisal of actual next verbs.

    ``fit``/``score_samples`` accept either:
    * a list of integer sequences (``list[list[int]]``), or
    * a pandas events DataFrame (sequences are built per-session internally).
    """

    layer = "L4"

    def __init__(self, hidden: int = 16, window: int = 5, epochs: int = 12,
                 use_torch: bool = True, version: str = "0.1.0") -> None:
        super().__init__(name="l4_deeplog", version=version)
        self.hidden = int(hidden)
        self.window = int(window)  # n-gram / lstm context length
        self.epochs = int(epochs)
        self.use_torch = bool(use_torch)
        self.vocab_size = 0
        self._model = None
        self._ngram: Optional[dict] = None
        self._vocab: dict[str, int] = {}

    # -- input coercion -------------------------------------------------- #
    def _to_seqs(self, X) -> list[list[int]]:
        if hasattr(X, "columns"):  # DataFrame of events
            seqs, _, vocab = build_verb_sequences(X, by="session")
            if not self._vocab:
                self._vocab = vocab
            return seqs
        return [list(map(int, s)) for s in X]

    @property
    def _backend_is_torch(self) -> bool:
        return self.use_torch and HAS_TORCH and self._model is not None

    # -- training -------------------------------------------------------- #
    def fit(self, X, y=None) -> "DeepLog":
        seqs = self._to_seqs(X)
        self.vocab_size = max((max(s) for s in seqs if s), default=0) + 2
        if self.use_torch and HAS_TORCH:
            self._fit_torch(seqs)
        else:
            self._fit_ngram(seqs)
        self._fitted = True
        return self

    def _fit_ngram(self, seqs: list[list[int]]) -> None:
        # (context tuple) -> next-token counts. Laplace-smoothed at scoring time.
        counts: dict[tuple, np.ndarray] = defaultdict(lambda: np.zeros(self.vocab_size))
        ctx = self.window
        for s in seqs:
            for i in range(len(s)):
                lo = max(0, i - ctx)
                key = tuple(s[lo:i])
                counts[key][s[i]] += 1
        self._ngram = {k: v for k, v in counts.items()}

    def _fit_torch(self, seqs: list[list[int]]) -> None:
        import torch
        from torch import nn

        ctx = self.window
        xs, ys = [], []
        for s in seqs:
            for i in range(1, len(s)):
                lo = max(0, i - ctx)
                window = s[lo:i]
                window = [0] * (ctx - len(window)) + window  # left-pad
                xs.append(window)
                ys.append(s[i])
        if not xs:
            self._fit_ngram(seqs)
            return
        torch.manual_seed(1405)
        Xt = torch.tensor(xs, dtype=torch.long)
        Yt = torch.tensor(ys, dtype=torch.long)
        V, H = self.vocab_size, self.hidden

        class _LSTM(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.emb = nn.Embedding(V, H)
                self.lstm = nn.LSTM(H, H, batch_first=True)
                self.fc = nn.Linear(H, V)

            def forward(self, x):
                e = self.emb(x)
                o, _ = self.lstm(e)
                return self.fc(o[:, -1, :])

        model = _LSTM()
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        lossf = nn.CrossEntropyLoss()
        model.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            logits = model(Xt)
            loss = lossf(logits, Yt)
            loss.backward()
            opt.step()
        model.eval()
        self._model = model

    # -- scoring --------------------------------------------------------- #
    def _seq_surprisal(self, s: list[int]) -> float:
        ctx = self.window
        if not s:
            return 0.0
        surprisals = []
        if self._backend_is_torch:
            import torch

            xs = []
            for i in range(1, len(s)):
                lo = max(0, i - ctx)
                w = s[lo:i]
                w = [0] * (ctx - len(w)) + w
                xs.append(w)
            if not xs:
                return 0.0
            with torch.no_grad():
                logits = self._model(torch.tensor(xs, dtype=torch.long))
                logp = torch.log_softmax(logits, dim=1).numpy()
            for j, i in enumerate(range(1, len(s))):
                tok = s[i] if s[i] < logp.shape[1] else 0
                surprisals.append(-logp[j, tok])
        else:
            for i in range(1, len(s)):
                lo = max(0, i - ctx)
                key = tuple(s[lo:i])
                counts = self._ngram.get(key) if self._ngram else None
                if counts is None:
                    surprisals.append(np.log(self.vocab_size))  # fully surprising
                    continue
                probs = (counts + 1.0) / (counts.sum() + self.vocab_size)
                tok = s[i] if s[i] < probs.shape[0] else 0
                surprisals.append(-np.log(probs[tok]))
        return float(np.mean(surprisals)) if surprisals else 0.0

    def score_samples(self, X) -> np.ndarray:
        seqs = self._to_seqs(X)
        raw = np.array([self._seq_surprisal(s) for s in seqs], dtype=float)
        return normalize_scores(raw, method="minmax")

    def explain(self, X, top_k: int = 3) -> list[list[ReasonCode]]:
        seqs = self._to_seqs(X)
        out: list[list[ReasonCode]] = []
        inv = {v: k for k, v in self._vocab.items()} if self._vocab else {}
        for s in seqs:
            sup = self._seq_surprisal(s)
            last = inv.get(s[-1], str(s[-1] if s else "")) if s else ""
            out.append([ReasonCode(source="attention", code="DEEPLOG_NEXT_EVENT",
                                   feature=str(last),
                                   detail="low predicted probability of next verb",
                                   contribution=float(sup))])
        return out


__all__ = ["DeepLog"]
