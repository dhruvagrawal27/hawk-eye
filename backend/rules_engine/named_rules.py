"""Named deterministic L1 rules (BACKEND-5, blueprint Part 20.1 / 24.5).

Each rule is a pure predicate ``(ctx, cfg) -> RuleHit | None`` reading L0 event fields + online
features. Thresholds come from the hot-reloadable YAML (``cfg.params``) so changing a threshold is
a four-eyes rule change (BACKEND-8), not a code change. Provenance codes are emitted into
``reason_codes`` verbatim (e.g. ``NEW_BENEFICIARY_THEN_HIGHVALUE``).
"""

from __future__ import annotations

from collections.abc import Callable

from rules_engine.context import RuleContext
from rules_engine.rule import RuleConfig, RuleHit

Predicate = Callable[[RuleContext, RuleConfig], "RuleHit | None"]


def fmt_inr(amount: int) -> str:
    """Indian digit grouping, e.g. 4800000 -> '48,00,000'."""
    s = str(int(amount))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


# --- The named rules (Part 24.5 / §7.2) -----------------------------------------------------
def swift_cbs_mismatch(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """SWIFT message with no matching CBS transaction (the PNB control; linkage SWIFT↔CBS)."""
    is_swift = ctx.channel == "swift" or "swift" in ctx.verb
    if not is_swift:
        return None
    has_swift_ref = bool(ctx.linkage.get("swift_ref"))
    no_cbs = not ctx.linkage.get("cbs_txn_id")
    feature_flag = bool(ctx.feat("swift_without_cbs_match"))
    if (has_swift_ref and no_cbs) or feature_flag:
        ref = ctx.linkage.get("swift_ref", "<swift>")
        return _hit(cfg, f"SWIFT message {ref} has no matching CBS transaction (recon mismatch)", 0.95)
    return None


def new_beneficiary_then_highvalue(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """New beneficiary created then a high-value payment within a short latency window."""
    pay_verbs = set(cfg.params.get("payment_verbs", ["approve_payment", "payment", "transfer"]))
    if ctx.verb not in pay_verbs:
        return None
    high_value = int(cfg.params.get("high_value_inr", 1_000_000))
    window_min = float(cfg.params.get("window_minutes", 60))
    max_age_days = float(cfg.params.get("new_beneficiary_max_age_days", 1))
    if ctx.amount < high_value:
        return None
    latency = ctx.feat("minutes_since_new_beneficiary")
    age_days = ctx.feat("beneficiary_age_days")
    is_new = (latency is not None and latency <= window_min) or (
        age_days is not None and age_days <= max_age_days
    )
    if not is_new:
        return None
    ben = ctx.obj.get("beneficiary_id", "<new payee>")
    when = f"within {int(latency)} min" if latency is not None else "shortly after creation"
    return _hit(cfg, f"new payee {ben} paid INR {fmt_inr(ctx.amount)} {when}", 0.9)


def dormant_reactivation_drain(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """A dormant account reactivated then drained."""
    drain_verbs = set(cfg.params.get("drain_verbs", ["withdraw", "transfer", "payment", "approve_payment"]))
    if ctx.verb not in drain_verbs:
        return None
    dormant_days = float(cfg.params.get("dormant_days", 180))
    drain_min = int(cfg.params.get("drain_min_inr", 100_000))
    acct_dormant = ctx.feat("account_dormant_days")
    reactivated = bool(ctx.feat("account_recently_reactivated"))
    if acct_dormant is None and not reactivated:
        return None
    is_dormant = (acct_dormant is not None and acct_dormant >= dormant_days) or reactivated
    if is_dormant and ctx.amount >= drain_min:
        acct = ctx.obj.get("account_id", "<account>")
        return _hit(
            cfg,
            f"dormant account {acct} reactivated then drained INR {fmt_inr(ctx.amount)}",
            0.88,
        )
    return None


def db_write_without_app_txn(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Direct DB write with no corresponding application transaction (linkage app-txn↔DB-write)."""
    db_verbs = set(cfg.params.get("db_verbs", ["db_write", "direct_write", "update_record", "delete_record"]))
    is_db = ctx.channel in ("db", "database") or ctx.verb in db_verbs
    if not is_db:
        return None
    has_app_txn = bool(ctx.linkage.get("app_txn_id"))
    if not has_app_txn:
        target = ctx.linkage.get("db_write_id") or ctx.obj.get("account_id") or "<row>"
        return _hit(cfg, f"direct DB write {target} with no matching application transaction", 0.92)
    return None


def entitlement_self_grant(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Actor grants themselves an entitlement / privilege escalation."""
    grant_verbs = set(
        cfg.params.get(
            "grant_verbs",
            ["grant_entitlement", "add_entitlement", "role_assign", "privilege_escalation", "self_grant"],
        )
    )
    if ctx.verb not in grant_verbs:
        return None
    target = (
        ctx.obj.get("target_employee_id")
        or ctx.obj.get("grantee")
        or ctx.obj.get("subject")
        or ctx.linkage.get("target_employee_id")
    )
    is_self = (target is not None and target == ctx.actor_id) or bool(ctx.feat("is_self_grant"))
    if is_self:
        ent = ctx.obj.get("entitlement") or ctx.obj.get("role") or "privileged entitlement"
        return _hit(cfg, f"{ctx.actor_id} granted themselves {ent} (self-grant / privilege escalation)", 0.9)
    return None


def off_hours_activity(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Activity outside the actor's + peer baseline hours."""
    if ctx.is_off_hours:
        geo = ctx.context.get("geo", "")
        loc = f", {geo}" if geo else ""
        return _hit(cfg, f"activity outside actor & peer baseline hours{loc}", 0.4)
    return None


def just_under_threshold(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Amount structured just below a reporting/approval threshold."""
    thresholds = cfg.params.get("thresholds_inr", [1_000_000, 5_000_000])
    band = float(cfg.params.get("band", 0.05))  # within 5% below the threshold
    if ctx.amount <= 0:
        return None
    for thr in thresholds:
        thr = int(thr)
        if int(thr * (1 - band)) <= ctx.amount < thr:
            return _hit(
                cfg,
                f"amount INR {fmt_inr(ctx.amount)} structured just below threshold INR {fmt_inr(thr)}",
                0.6,
            )
    return None


def _hit(cfg: RuleConfig, detail: str, score: float) -> RuleHit:
    return RuleHit(
        code=cfg.code,
        version=cfg.version,
        severity=cfg.severity,
        hard_hit=cfg.hard_hit,
        detail=detail,
        score=score,
    )


# Registry: rule code → predicate. The YAML supplies config/params/version for each code.
NAMED_RULES: dict[str, Predicate] = {
    "SWIFT_CBS_MISMATCH": swift_cbs_mismatch,
    "NEW_BENEFICIARY_THEN_HIGHVALUE": new_beneficiary_then_highvalue,
    "DORMANT_REACTIVATION_DRAIN": dormant_reactivation_drain,
    "DB_WRITE_WITHOUT_APP_TXN": db_write_without_app_txn,
    "ENTITLEMENT_SELF_GRANT": entitlement_self_grant,
    "OFF_HOURS_ACTIVITY": off_hours_activity,
    "JUST_UNDER_THRESHOLD": just_under_threshold,
}
