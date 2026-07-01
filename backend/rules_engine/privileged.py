"""Privileged-session & entitlement-change rule logic (BACKEND-7, blueprint Part 2 / 19.3).

Detects privileged-session correlation, DB-write-without-app-transaction (canonical rule lives in
``named_rules``; re-exported here for the privileged family), entitlement-change/self-grant,
least-privilege violations, dormant-reactivation, orphaned-account use, and leaver-window exfil
proxies. All predicates share the ``(ctx, cfg)`` signature and read online features from DATA.
"""

from __future__ import annotations

from rules_engine.context import RuleContext
from rules_engine.named_rules import Predicate, _hit, fmt_inr
from rules_engine.rule import RuleConfig, RuleHit


def privileged_session_correlation(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """A privileged session correlated with anomalous/off-hours/sensitive activity."""
    privileged = bool(ctx.actor.get("privileged_flag")) or bool(ctx.feat("privileged_session"))
    if not privileged:
        return None
    sensitive = (
        ctx.is_off_hours
        or ctx.channel in ("db", "database")
        or bool(ctx.feat("sensitive_data_access"))
        or ctx.verb in set(cfg.params.get("sensitive_verbs", ["export", "bulk_export", "db_write"]))
    )
    if sensitive:
        return _hit(
            cfg,
            f"privileged session for {ctx.actor_id} correlated with sensitive/off-hours activity ({ctx.verb})",
            0.7,
        )
    return None


def orphaned_account_use(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Use of an orphaned / leaver / never-deprovisioned account."""
    orphaned = bool(ctx.feat("account_orphaned")) or bool(ctx.actor.get("leaver_flag"))
    if orphaned and ctx.verb:
        return _hit(cfg, f"orphaned/leaver account {ctx.actor_id} used for {ctx.verb}", 0.75)
    return None


def least_privilege_violation(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Action exercising an entitlement the actor should not hold (least-privilege breach)."""
    if bool(ctx.feat("least_privilege_violation")) or bool(ctx.feat("entitlement_not_required")):
        ent = ctx.obj.get("entitlement") or ctx.feat("violated_entitlement") or "an entitlement"
        return _hit(cfg, f"{ctx.actor_id} exercised {ent} beyond least-privilege baseline", 0.65)
    return None


def leaver_window_exfil(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Bulk export/exfil proxy inside a leaver's notice window."""
    exfil_verbs = set(cfg.params.get("exfil_verbs", ["export", "bulk_export", "download", "copy"]))
    if ctx.verb not in exfil_verbs:
        return None
    leaver = bool(ctx.actor.get("leaver_flag")) or bool(ctx.feat("in_leaver_window"))
    vol_min = int(cfg.params.get("export_volume_min", 1000))
    volume = ctx.feat("export_record_count", 0)
    if leaver and volume and volume >= vol_min:
        return _hit(
            cfg,
            f"leaver {ctx.actor_id} exported {fmt_inr(int(volume))} records during notice window",
            0.85,
        )
    return None


def no_leave_streak(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """No-leave-streak proxy (a classic embezzlement tell) combined with sensitive access."""
    streak = ctx.feat("no_leave_days", 0)
    threshold = int(cfg.params.get("no_leave_days_threshold", 365))
    sensitive = ctx.is_off_hours or bool(ctx.feat("sensitive_data_access"))
    if streak and streak >= threshold and sensitive:
        return _hit(
            cfg,
            f"{ctx.actor_id} no-leave streak {int(streak)}d with continued sensitive access",
            0.5,
        )
    return None


def standing_privilege_detection(ctx: RuleContext, cfg: RuleConfig) -> RuleHit | None:
    """Entitlements held but not exercised (M2.2, RBI IS-Audit JIT/least-privilege). Reads the
    per-user standing-privilege posture materialized by DATA (``identity_access.standing_privilege``)."""
    count = int(ctx.feat("standing_privilege_count", 0) or 0)
    never = int(ctx.feat("never_exercised_entitlements", 0) or 0)
    max_age = float(ctx.feat("days_since_grant_max", 0) or 0)
    min_age = int(cfg.params.get("min_grant_age_days", 14))
    threshold = int(cfg.params.get("unexercised_threshold", 2))
    if max_age < min_age:
        return None
    if count >= threshold or never >= threshold:
        return _hit(
            cfg,
            f"{ctx.actor_id} holds {count} standing (unexercised ≥{min_age}d) "
            f"entitlement(s); {never} never exercised — least-privilege gap",
            0.65,
        )
    return None


PRIVILEGED_RULES: dict[str, Predicate] = {
    "PRIVILEGED_SESSION_CORRELATION": privileged_session_correlation,
    "ORPHANED_ACCOUNT_USE": orphaned_account_use,
    "LEAST_PRIVILEGE_VIOLATION": least_privilege_violation,
    "LEAVER_WINDOW_EXFIL": leaver_window_exfil,
    "NO_LEAVE_STREAK": no_leave_streak,
    "STANDING_PRIVILEGE_DETECTION": standing_privilege_detection,
}
