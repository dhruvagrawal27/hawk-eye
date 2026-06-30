"""Explanation-manipulation defenses (ML-27; blueprint Part 19.2, 20.6).

SHAP-style explanations are adversarially manipulable: an attacker (or a buggy/poisoned
explainer) can produce a plausible-looking explanation that does NOT actually reflect why
the alert fired, to mislead the investigator. The blueprint's mitigation: prefer
INTERPRETABLE components + RULE PROVENANCE, and CROSS-CHECK every explanation against the
deterministic rules and the raw evidence. An explanation that contradicts the rules or
cites facts absent from the raw evidence is flagged.

* :func:`cross_check_explanation`        — the core check (rules + raw evidence vs claim).
* :class:`ExplanationConsistencyDefense` — stateful wrapper bundling rule provenance.

ALERT-ONLY: a flagged explanation is surfaced for human review; nothing blocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ml.base import ReasonCode


@dataclass
class ExplanationCheck:
    """Outcome of cross-checking a model explanation against rules + raw evidence."""

    consistent: bool
    contradicts_rules: list[str] = field(default_factory=list)
    unsupported_features: list[str] = field(default_factory=list)
    missing_dominant_rules: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def flagged(self) -> bool:
        return not self.consistent

    def to_dict(self) -> dict[str, Any]:
        return {
            "consistent": self.consistent,
            "flagged": self.flagged,
            "contradicts_rules": list(self.contradicts_rules),
            "unsupported_features": list(self.unsupported_features),
            "missing_dominant_rules": list(self.missing_dominant_rules),
            "detail": self.detail,
        }


def _rc_to_dict(rc: Any) -> dict[str, Any]:
    if isinstance(rc, dict):
        return rc
    to_dict = getattr(rc, "to_dict", None)
    return to_dict() if callable(to_dict) else {}


def _explanation_features(explanation: Iterable[Any]) -> dict[str, float]:
    """Pull {feature: |contribution|} from an explanation (ReasonCodes or dicts)."""
    feats: dict[str, float] = {}
    for rc in explanation:
        d = _rc_to_dict(rc)
        name = d.get("feature") or d.get("code")
        if name is None:
            continue
        contrib = abs(float(d.get("contribution", 0.0) or 0.0))
        feats[str(name)] = max(feats.get(str(name), 0.0), contrib)
    return feats


def cross_check_explanation(
    explanation: Iterable[Any],
    *,
    fired_rules: Iterable[str],
    raw_evidence: dict[str, Any],
    raw_atol: float = 1e-9,
) -> ExplanationCheck:
    """Cross-check a model explanation against the deterministic rules + raw evidence.

    An explanation is INCONSISTENT (flagged) if any of:

      * **Unsupported feature** — it attributes meaningful weight to a feature that has no
        presence in ``raw_evidence`` (value missing or ~0). A manipulated explanation that
        invents a benign driver to distract the investigator trips this.
      * **Contradicts rules** — it claims a rule did NOT fire / understates a feature that a
        deterministic rule says DID fire on strong raw evidence.
      * **Missing dominant rule** — a rule fired on strong raw evidence but the explanation
        never mentions it at all (the manipulation hides the real driver).

    ``fired_rules`` are deterministic rule codes (ground truth); ``raw_evidence`` is the
    feature->value map the alert was actually computed from.
    """
    feats = _explanation_features(explanation)
    explained = set(feats)
    fired = {str(r) for r in fired_rules}

    # 1. Features claimed by the explanation that the raw evidence does not support.
    unsupported: list[str] = []
    for name, contrib in feats.items():
        if contrib <= raw_atol:
            continue
        val = raw_evidence.get(name)
        if val is None or (_is_number(val) and abs(float(val)) <= raw_atol):
            unsupported.append(name)

    # 2/3. Rules that fired on strong raw evidence but the explanation omits / contradicts.
    missing_dominant: list[str] = []
    contradicts: list[str] = []
    for rule in fired:
        rule_evidence = raw_evidence.get(rule)
        strong = (
            rule_evidence is None
            or (not _is_number(rule_evidence))
            or abs(float(rule_evidence)) > raw_atol
        )
        if not strong:
            continue
        # Does the explanation reference this rule (by code or by an associated feature)?
        referenced = rule in explained or any(rule in f or f in rule for f in explained)
        if not referenced:
            missing_dominant.append(rule)

    # An explanation whose TOP-WEIGHTED feature is unsupported while a real rule is omitted
    # is the canonical manipulation -> explicit contradiction.
    if feats and unsupported:
        top = max(feats, key=lambda k: feats[k])
        if top in unsupported and missing_dominant:
            contradicts.append(
                f"top driver {top!r} is unsupported by raw evidence while fired rule(s) "
                f"{missing_dominant} are omitted"
            )

    consistent = not (unsupported or missing_dominant or contradicts)
    detail = (
        "explanation consistent with rules + raw evidence"
        if consistent
        else (
            f"unsupported={unsupported}; missing_dominant_rules={missing_dominant}; "
            f"contradicts={contradicts}"
        )
    )
    return ExplanationCheck(
        consistent=consistent,
        contradicts_rules=contradicts,
        unsupported_features=unsupported,
        missing_dominant_rules=missing_dominant,
        detail=detail,
    )


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class ExplanationConsistencyDefense:
    """Stateful explanation cross-checker that also emits rule-provenance reason codes.

    Prefers interpretable components: it carries the deterministic ``fired_rules`` (the
    trustworthy provenance) and validates any model-produced explanation against them and
    the raw evidence. ``provenance_reason_codes`` returns the rule-sourced reason codes a
    human can always fall back to when a model explanation is flagged.
    """

    def __init__(self, *, raw_atol: float = 1e-9) -> None:
        self.raw_atol = float(raw_atol)

    def check(
        self,
        explanation: Iterable[Any],
        *,
        fired_rules: Iterable[str],
        raw_evidence: dict[str, Any],
    ) -> ExplanationCheck:
        return cross_check_explanation(
            explanation,
            fired_rules=fired_rules,
            raw_evidence=raw_evidence,
            raw_atol=self.raw_atol,
        )

    @staticmethod
    def provenance_reason_codes(
        fired_rules: Iterable[str], raw_evidence: dict[str, Any]
    ) -> list[ReasonCode]:
        """Trustworthy rule-provenance reason codes (the interpretable fallback)."""
        out: list[ReasonCode] = []
        for rule in fired_rules:
            val = raw_evidence.get(str(rule))
            detail = f"rule {rule} fired"
            if val is not None:
                detail += f" (evidence={val})"
            out.append(ReasonCode(source="rule", code=str(rule), detail=detail))
        return out
