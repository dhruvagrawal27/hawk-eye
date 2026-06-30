"""Model-inversion / membership-inference defenses (ML-27; blueprint Part 19.2).

If an attacker can query the model freely and read raw scores, they can (a) invert it to
reconstruct training records / reverse-engineer the decision surface, and (b) run
membership-inference to learn whether a specific person was in the training set. The
blueprint's mitigations:

* :class:`InternalInferenceAPI` — the inference surface is INTERNAL-ONLY and AUTHENTICATED;
  it is RATE-LIMITED; and it NEVER returns a raw score externally — only a coarse risk
  BAND (low/medium/high/critical). Raw scores stay server-side for the (trusted) fusion
  path; external callers get banded output, which destroys the precision needed for
  gradient-free inversion and membership inference.
* :class:`ExtractionMonitor`    — watches each principal's query stream for model-extraction
  patterns (high volume, near-duplicate probing, boundary sweeping) and flags it.

ALERT-ONLY: extraction detection raises a flag for a human; it does not auto-ban.
Secrets (API tokens) come from ``os.environ`` / the caller — never hardcoded.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

import numpy as np

from ml.base.interfaces import Severity, severity_from_score
from ml.narrative.guardrails import RateLimiter


class InferenceDenied(RuntimeError):
    """Raised when an inference request is unauthenticated, rate-limited, or external-raw."""


# --------------------------------------------------------------------------- #
# Score banding (coarsening) — never expose raw scores externally             #
# --------------------------------------------------------------------------- #
@dataclass
class BandedScore:
    """The ONLY thing an external caller may receive: a coarse band, no raw number."""

    band: str  # low | medium | high | critical
    band_index: int  # 0..3 (ordinal, still coarse)
    model_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "band": self.band,
            "band_index": self.band_index,
            "model_version": self.model_version,
        }


_BAND_ORDER = (Severity.LOW, Severity.MEDIUM, Severity.HIGH)


def band_score(score: float, *, model_version: str = "") -> BandedScore:
    """Coarsen a raw [0,1] score into a 3-way band (reuses the L6 severity bands).

    The raw probability is discarded; only the band survives, so a membership/inversion
    attacker cannot read the fine-grained signal they need.
    """
    sev = severity_from_score(float(score) * 100.0)
    return BandedScore(
        band=sev.value, band_index=_BAND_ORDER.index(sev), model_version=model_version
    )


# --------------------------------------------------------------------------- #
# Extraction-pattern monitoring                                               #
# --------------------------------------------------------------------------- #
@dataclass
class ExtractionAlert:
    principal: str
    suspected: bool
    n_queries: int
    duplicate_ratio: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "principal": self.principal,
            "suspected": self.suspected,
            "n_queries": self.n_queries,
            "duplicate_ratio": round(float(self.duplicate_ratio), 4),
            "reasons": list(self.reasons),
        }


class ExtractionMonitor:
    """Detect model-extraction query patterns per principal.

    Heuristics (any of which trips a flag):
      * **Volume**: more than ``max_queries`` within ``window_seconds`` (systematic harvest).
      * **Boundary probing**: a high ratio of near-duplicate query vectors (the attacker
        perturbs one feature at a time to map the decision boundary).
    """

    def __init__(
        self,
        *,
        max_queries: int = 100,
        window_seconds: float = 60.0,
        dup_ratio_thresh: float = 0.5,
        dup_atol: float = 1e-3,
    ) -> None:
        self.max_queries = int(max_queries)
        self.window_seconds = float(window_seconds)
        self.dup_ratio_thresh = float(dup_ratio_thresh)
        self.dup_atol = float(dup_atol)
        self._times: dict[str, deque[float]] = defaultdict(deque)
        self._recent_vecs: dict[str, deque[np.ndarray]] = defaultdict(
            lambda: deque(maxlen=256)
        )

    def observe(
        self, principal: str, features: Sequence[float], *, now: Optional[float] = None
    ) -> ExtractionAlert:
        now = time.time() if now is None else now
        vec = np.asarray(list(features), dtype=float).ravel()

        times = self._times[principal]
        times.append(now)
        while times and now - times[0] > self.window_seconds:
            times.popleft()

        recent = self._recent_vecs[principal]
        # Count how many recent vectors are near-duplicates of this one (boundary sweeping).
        n_dup = sum(
            1
            for v in recent
            if v.shape == vec.shape and np.allclose(v, vec, atol=self.dup_atol)
        )
        recent.append(vec)
        dup_ratio = n_dup / max(len(recent), 1)

        reasons: list[str] = []
        if len(times) > self.max_queries:
            reasons.append(
                f"volume: {len(times)} queries in {self.window_seconds:.0f}s window"
            )
        if dup_ratio >= self.dup_ratio_thresh and len(recent) >= 5:
            reasons.append(
                f"boundary-probing: {dup_ratio:.2f} near-duplicate query ratio"
            )
        return ExtractionAlert(
            principal=str(principal),
            suspected=bool(reasons),
            n_queries=len(times),
            duplicate_ratio=dup_ratio,
            reasons=reasons,
        )


# --------------------------------------------------------------------------- #
# Internal-only authenticated, rate-limited inference API wrapper             #
# --------------------------------------------------------------------------- #
class InternalInferenceAPI:
    """Authenticated, rate-limited, INTERNAL-ONLY inference wrapper.

    Wraps any ``predict_fn(features) -> raw_score in [0,1]``. Rules:

      * **Authentication** — every call needs a token in ``authorized_tokens`` (supplied by
        the caller, e.g. from ``os.environ``); unknown tokens are denied.
      * **Internal vs external** — internal (trusted, attested) callers may request the raw
        score; EXTERNAL callers can NEVER get it — they receive a :class:`BandedScore`.
        ``infer`` with ``raw=True`` from an external principal raises.
      * **Rate limiting** — per-principal sliding window (reuses the narrative
        :class:`~ml.narrative.guardrails.RateLimiter`).
      * **Extraction monitoring** — every query feeds :class:`ExtractionMonitor`; a tripped
        pattern raises an advisory flag (still returns a band, never blocks the bank).
    """

    def __init__(
        self,
        predict_fn: Callable[[Any], float],
        *,
        authorized_tokens: dict[str, str],
        model_version: str = "model@0.0.0",
        max_calls: int = 60,
        per_seconds: float = 60.0,
        extraction_monitor: Optional[ExtractionMonitor] = None,
    ) -> None:
        self._predict = predict_fn
        # token -> scope ("internal" | "external"); never hardcoded — caller passes them in.
        self._tokens = dict(authorized_tokens)
        self.model_version = model_version
        self._limiter = RateLimiter(max_calls=max_calls, per_seconds=per_seconds)
        self._monitor = extraction_monitor or ExtractionMonitor()
        self._extraction_flags: list[ExtractionAlert] = []

    def _authenticate(self, token: str) -> str:
        scope = self._tokens.get(token)
        if scope is None:
            raise InferenceDenied("unauthenticated: unknown or missing API token")
        return scope

    def infer(
        self,
        features: Sequence[float],
        *,
        token: str,
        principal: str,
        raw: bool = False,
        now: Optional[float] = None,
    ) -> BandedScore | float:
        """Run inference. External principals ALWAYS get a band; raw=True is internal-only."""
        scope = self._authenticate(token)

        if not self._limiter.allow(principal, now=now):
            raise InferenceDenied(
                f"rate limited: principal {principal!r} exceeded quota"
            )

        alert = self._monitor.observe(principal, features, now=now)
        if alert.suspected:
            self._extraction_flags.append(alert)

        raw_score = float(np.clip(self._predict(features), 0.0, 1.0))

        if raw:
            if scope != "internal":
                # Hard rule: raw scores NEVER leave to an external/untrusted caller.
                raise InferenceDenied(
                    "raw scores are internal-only; external callers receive a banded score"
                )
            return raw_score

        # Default (and the only thing external callers can ever get): a coarse band.
        return band_score(raw_score, model_version=self.model_version)

    def extraction_flags(self) -> list[ExtractionAlert]:
        return list(self._extraction_flags)
