"""L6.5 — Privileged-action policy engine (the PDP core, M3.1).

Maps a privileged STAFF action + its risk context to ``ALLOW | STEP_UP | HOLD_FOR_REVIEW``. Mirrors
the L1 RulesEngine shape (a predicate/policy registry + hot-reloadable YAML) but is self-contained so
the action-gate runs as its own service/container.

ALERT-ONLY by construction: the engine governs only REVERSIBLE staff actions (entitlement self-grant,
SWIFT/SO message, bulk export, direct DB write, same-actor maker+checker, toxic-combination). It has
**no money-movement path** — ``object.amount`` is deliberately never read — so it can never block,
hold, or delay a payment. STEP_UP/HOLD are reversible; the SOURCE system enforces the decision, the
gate only authors policy + records audit.

Aggregation: any ``hard_gate`` match OR SoD ≥ 0.9 OR OPA-deny → HOLD_FOR_REVIEW; any soft match over
threshold → STEP_UP; else ALLOW.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

_POLICIES_YAML = Path(__file__).parent / "policies" / "policies.yaml"
_HARD_SOD_THRESHOLD = 0.9


class Decision(str, Enum):
    ALLOW = "ALLOW"
    STEP_UP = "STEP_UP"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"


_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass
class Policy:
    code: str
    name: str
    verbs: set[str]
    gate: str  # "hard" -> HOLD ; "soft" -> STEP_UP
    severity: str = "medium"
    enabled: bool = True
    # optional online-feature conditions (all must be truthy for the policy to apply)
    require_features: tuple[str, ...] = ()

    def matches(self, verb: str, features: dict) -> bool:
        if not self.enabled:
            return False
        if self.verbs and verb not in self.verbs:
            return False
        return all(bool(features.get(f)) for f in self.require_features)


# Default policy set (the editable store is policies/policies.yaml; these are the shipped defaults).
DEFAULT_POLICIES: tuple[Policy, ...] = (
    Policy("SELF_GRANT_HOLD", "Entitlement self-grant",
           {"grant_entitlement", "self_grant", "add_entitlement", "role_assign"}, "hard", "high"),
    Policy("MAKER_CHECKER_SAME_ACTOR_HOLD", "Maker+checker by the same actor",
           set(), "hard", "high", require_features=("maker_checker_same_actor",)),
    Policy("BULK_EXPORT_HOLD", "Bulk export from a privileged session",
           {"export", "bulk_export", "download"}, "hard", "high",
           require_features=("bulk_export_high_volume",)),
    Policy("SWIFT_SEND_STEP_UP", "SWIFT / SO message send",
           {"swift_send", "so_send", "lou_issue"}, "soft", "high"),
    Policy("DB_WRITE_STEP_UP", "Direct DB write",
           {"db_write", "direct_write", "update_record", "delete_record"}, "soft", "medium"),
    Policy("BULK_EXPORT_STEP_UP", "Bulk export (below mass threshold)",
           {"export", "bulk_export", "download"}, "soft", "medium"),
)


@dataclass
class PolicyDecision:
    decision: Decision
    severity: str
    reason_codes: list[dict] = field(default_factory=list)
    matched: list[str] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None


class ActionGate:
    """Evaluate a privileged staff action against the policy set → a PolicyDecision."""

    def __init__(self, policies: tuple[Policy, ...] | None = None) -> None:
        self._policies = policies or self._load() or DEFAULT_POLICIES

    def _load(self) -> tuple[Policy, ...] | None:
        try:
            import yaml  # optional; fall back to DEFAULT_POLICIES if absent
        except Exception:
            return None
        if not _POLICIES_YAML.exists():
            return None
        data = yaml.safe_load(_POLICIES_YAML.read_text(encoding="utf-8")) or {}
        out: list[Policy] = []
        for p in data.get("policies", []):
            out.append(Policy(
                code=p["code"], name=p.get("name", p["code"]),
                verbs=set(p.get("verbs", [])), gate=p.get("gate", "soft"),
                severity=p.get("severity", "medium"), enabled=bool(p.get("enabled", True)),
                require_features=tuple(p.get("require_features", [])),
            ))
        return tuple(out) or None

    @property
    def fingerprint(self) -> str:
        raw = ";".join(sorted(p.code for p in self._policies if p.enabled))
        return "policies-" + hashlib.sha256(raw.encode()).hexdigest()[:8]

    def known_codes(self) -> set[str]:
        return {p.code for p in self._policies}

    def evaluate(
        self,
        verb: str,
        features: dict | None = None,
        *,
        sod_score: float = 0.0,
        opa_deny: bool = False,
        governance_available: bool = True,
        privileged: bool = False,
    ) -> PolicyDecision:
        features = features or {}
        verb = (verb or "").lower()

        # Degradation: governance unavailable → fail CLOSED for privileged verbs (HOLD), fail OPEN
        # (ALLOW) for routine — a privileged action is NEVER silently allowed.
        if not governance_available:
            if privileged or verb in _PRIVILEGED_VERBS:
                return PolicyDecision(
                    Decision.HOLD_FOR_REVIEW, "high",
                    [{"source": "gate", "code": "GOVERNANCE_UNAVAILABLE",
                      "detail": "governance store unavailable — privileged action held pending review"}],
                    degraded=True, degraded_reason="governance_unavailable",
                )
            return PolicyDecision(Decision.ALLOW, "low", degraded=True,
                                  degraded_reason="governance_unavailable")

        matched_hard: list[Policy] = []
        matched_soft: list[Policy] = []
        reason_codes: list[dict] = []
        for p in self._policies:
            if p.matches(verb, features):
                (matched_hard if p.gate == "hard" else matched_soft).append(p)
                reason_codes.append({
                    "source": "policy", "code": p.code,
                    "detail": f"{p.name} ({'hard-gate' if p.gate == 'hard' else 'step-up'})",
                })

        if sod_score >= _HARD_SOD_THRESHOLD:
            matched_hard.append(Policy("SOD_TOXIC", "SoD toxic combination", set(), "hard", "high"))
            reason_codes.append({"source": "sod", "code": "SOD_TOXIC",
                                 "detail": f"SoD score {sod_score:.2f} ≥ {_HARD_SOD_THRESHOLD}"})
        if opa_deny:
            matched_hard.append(Policy("OPA_DENY", "OPA entitlement deny", set(), "hard", "high"))
            reason_codes.append({"source": "opa", "code": "OPA_DENY",
                                 "detail": "OPA entitlement policy denied the action"})

        if matched_hard:
            decision = Decision.HOLD_FOR_REVIEW
            sev = "high"
        elif matched_soft:
            decision = Decision.STEP_UP
            sev = _max_sev(matched_soft)
        else:
            decision = Decision.ALLOW
            sev = "low"
        return PolicyDecision(
            decision=decision, severity=sev, reason_codes=reason_codes,
            matched=[p.code for p in (matched_hard + matched_soft)],
        )


_PRIVILEGED_VERBS = {
    "grant_entitlement", "self_grant", "add_entitlement", "role_assign",
    "swift_send", "so_send", "lou_issue", "db_write", "direct_write",
    "delete_record", "export", "bulk_export",
}


def _max_sev(policies: list[Policy]) -> str:
    best = "low"
    for p in policies:
        if _SEVERITY_RANK.get(p.severity, 0) > _SEVERITY_RANK.get(best, 0):
            best = p.severity
    return best


GATE = ActionGate()
