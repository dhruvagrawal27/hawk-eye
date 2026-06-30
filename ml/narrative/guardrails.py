"""Narrative guardrails (ML-12; Part 25.7).

Output is advisory and labelled "AI-generated"; the prompt forbids fabrication and
de-anonymisation; and — the load-bearing check — the narrative is GROUNDED against the
structured reason codes: if it introduces a fact (a number or an identifier token) not
present in the evidence, it is flagged/rejected. Plus a simple rate limiter.
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

AI_GENERATED_LABEL = "AI-generated · advisory only · not a decision"

# Identifier tokens use the known Hawk-Eye entity prefixes only, so generic hyphenated
# words like "AI-generated" or "maker-checker" are NOT mistaken for identifiers.
_ID_PREFIXES = ("EMP", "ACCT", "BEN", "RNG", "WS", "BR", "PG", "VEN", "DEV", "SESS", "ACC")
_TOKEN_RE = re.compile(r"\b(?:" + "|".join(_ID_PREFIXES) + r")-[A-Za-z0-9]+\b")
# Numbers with optional grouping separators / decimals (48,00,000 or 4800000 or 0.82).
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Generic scale numbers a narrative may legitimately use (risk is out of 100, etc.).
_TOLERATED_SCALE = {"100", "1000", "10000", "100000"}


def _norm_num(s: str) -> str:
    return s.replace(",", "")


def _collect_facts(text: str) -> tuple[set[str], set[str]]:
    text = text or ""
    tokens = set(_TOKEN_RE.findall(text))
    # Extract numbers AFTER removing identifier tokens, so hex token fragments
    # (e.g. EMP-7f3a -> "7","3a") never pollute the number set.
    text_wo_tokens = _TOKEN_RE.sub(" ", text)
    numbers = {_norm_num(m) for m in _NUM_RE.findall(text_wo_tokens)}
    return tokens, numbers


def _evidence_text(alert_ctx: dict[str, Any]) -> str:
    """Flatten the alert context + reason codes into a single evidence string."""
    parts: list[str] = []
    for key in ("alert_id", "entity_id", "risk_score", "severity", "confidence", "exposure_inr"):
        if alert_ctx.get(key) is not None:
            parts.append(str(alert_ctx[key]))
    for rc in alert_ctx.get("reason_codes", []) or []:
        rc = rc if isinstance(rc, dict) else getattr(rc, "to_dict", lambda: {})()
        for v in rc.values():
            parts.append(str(v))
    for layer in alert_ctx.get("contributing_layers", []) or []:
        parts.append(str(layer))
    return " ".join(parts)


@dataclass
class GroundingResult:
    grounded: bool
    ungrounded_tokens: list[str] = field(default_factory=list)
    ungrounded_numbers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "grounded": self.grounded,
            "ungrounded_tokens": self.ungrounded_tokens,
            "ungrounded_numbers": self.ungrounded_numbers,
        }


def check_grounding(narrative: str, alert_ctx: dict[str, Any], *, number_tolerance: bool = True) -> GroundingResult:
    """Flag identifier tokens / numbers in the narrative that are not in the evidence.

    A small allow-list of generic numbers (clock-ish small ints, percentages) is tolerated
    so phrasing like "within 27 minutes" is not falsely flagged when 27 is in evidence.
    """
    ev_tokens, ev_numbers = _collect_facts(_evidence_text(alert_ctx))
    nar_tokens, nar_numbers = _collect_facts(narrative or "")

    bad_tokens = sorted(t for t in nar_tokens if t not in ev_tokens)
    bad_numbers = []
    for n in sorted(nar_numbers):
        if n in ev_numbers:  # exact (comma-normalised) match to an evidence number
            continue
        if number_tolerance and len(n.replace(".", "")) <= 2:  # small generic ints (hours, counts, %)
            continue
        if number_tolerance and n in _TOLERATED_SCALE:  # risk-out-of-100 style scale numbers
            continue
        bad_numbers.append(n)
    return GroundingResult(grounded=not (bad_tokens or bad_numbers),
                           ungrounded_tokens=bad_tokens, ungrounded_numbers=bad_numbers)


def label_ai_generated(response: dict[str, Any]) -> dict[str, Any]:
    """Annotate a narrate() response as AI-generated/advisory (never triggers an action)."""
    out = dict(response)
    out["ai_generated"] = True
    out["advisory"] = True
    out["label"] = AI_GENERATED_LABEL
    return out


class RateLimiter:
    """Sliding-window rate limiter (Part 25.7). Keyed by alert/entity id."""

    def __init__(self, max_calls: int = 30, per_seconds: float = 60.0) -> None:
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        dq = self._hits.setdefault(key, deque())
        while dq and now - dq[0] > self.per_seconds:
            dq.popleft()
        if len(dq) >= self.max_calls:
            return False
        dq.append(now)
        return True
