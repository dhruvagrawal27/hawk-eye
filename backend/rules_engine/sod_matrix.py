"""SoD / toxic-combination matrix scoring engine (BACKEND-6, blueprint Part 3.4 / 0 / 8).

Scores an event against a configurable Separation-of-Duties matrix and emits toxic-combination
flags: maker+checker same actor, create+approve by the same isolated maker-checker pair,
self-grant entitlement, and held-entitlement conflicts (a single actor holding two duties that
must be separated). OPA (``opa/entitlement.rego``) evaluates the least-privilege/entitlement
logic; this Python engine is the authoritative local evaluator and stays in lockstep.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rules_engine.context import RuleContext

# Default toxic entitlement conflicts — any actor holding BOTH sides of a pair is a SoD breach.
# Configurable via rules_engine/rules/sod_matrix.yaml (DATABASE/Compliance own the bank matrix).
DEFAULT_CONFLICTS: list[frozenset[str]] = [
    frozenset({"create_beneficiary", "approve_payment"}),
    frozenset({"create_vendor", "approve_payment"}),
    frozenset({"initiate_loan", "approve_loan"}),
    frozenset({"create_user", "grant_entitlement"}),
    frozenset({"maker", "checker"}),
    frozenset({"trade_capture", "trade_settlement"}),
]


@dataclass(frozen=True)
class SoDFlag:
    code: str
    detail: str
    score: float
    combo: tuple[str, ...] = ()

    def to_reason_code(self) -> dict:
        return {"source": "rule", "code": self.code, "detail": self.detail}


@dataclass
class SoDResult:
    flags: list[SoDFlag] = field(default_factory=list)
    score: float = 0.0

    @property
    def fired(self) -> bool:
        return bool(self.flags)


class SoDMatrix:
    def __init__(self, conflicts: list[frozenset[str]] | None = None):
        self.conflicts = conflicts if conflicts is not None else list(DEFAULT_CONFLICTS)

    def score(self, ctx: RuleContext) -> SoDResult:
        flags: list[SoDFlag] = []

        # 1) Same actor as maker AND checker.
        same_actor = bool(ctx.feat("maker_checker_same_actor"))
        creator = ctx.feat("beneficiary_created_by") or ctx.feat("maker_actor")
        if not same_actor and ctx.maker_checker == "checker" and creator == ctx.actor_id and creator:
            same_actor = True
        if same_actor:
            flags.append(
                SoDFlag(
                    "SOD_MAKER_CHECKER_SAME_ACTOR",
                    f"{ctx.actor_id} acted as both maker and checker on the same transaction",
                    0.95,
                    ("maker", "checker"),
                )
            )

        # 2) Create + approve by the same isolated maker-checker pair (collusion ring candidate).
        if bool(ctx.feat("maker_checker_pair_isolated")):
            partner = ctx.feat("maker_checker_partner", "<partner>")
            flags.append(
                SoDFlag(
                    "SOD_CREATE_APPROVE_ISOLATED_PAIR",
                    f"maker {ctx.actor_id} + checker {partner} recur as an isolated pair",
                    0.85,
                    ("create", "approve"),
                )
            )

        # 3) Self-grant entitlement (toxic create+approve of one's own access).
        target = ctx.obj.get("target_employee_id") or ctx.obj.get("grantee")
        if bool(ctx.feat("is_self_grant")) or (target and target == ctx.actor_id):
            flags.append(
                SoDFlag(
                    "SOD_SELF_GRANT_ENTITLEMENT",
                    f"{ctx.actor_id} created and approved their own entitlement",
                    0.9,
                    ("grant", "approve"),
                )
            )

        # 4) Held-entitlement conflicts — one actor holding both sides of a separated duty.
        held = {str(e).lower() for e in (ctx.feat("held_entitlements") or [])}
        if held:
            for conflict in self.conflicts:
                if conflict <= held:
                    combo = tuple(sorted(conflict))
                    flags.append(
                        SoDFlag(
                            "SOD_TOXIC_ENTITLEMENT_COMBINATION",
                            f"{ctx.actor_id} holds conflicting duties {combo[0]} + {combo[1]}",
                            0.8,
                            combo,
                        )
                    )

        total = min(1.0, max((f.score for f in flags), default=0.0))
        return SoDResult(flags=flags, score=total)


DEFAULT_SOD_MATRIX = SoDMatrix()
