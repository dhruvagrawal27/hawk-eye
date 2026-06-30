"""Retention & archival tiering job (DATABASE-9).

Ages data **hot ClickHouse → cold object store → archive** across all stores,
keyed to DPDP retention + RBI record-keeping and DATA CLASSIFICATION (Part 28.2),
with a confirmed-fraud carve-out (longer hold). The hard invariant: **never
expire or shorten an object-lock/WORM object below its lock period** — the job
refuses and logs.

Design: pure-Python *planner* (no infra) + guarded *appliers* (ClickHouse / MinIO
clients optional). `--plan` prints the actions; `--apply` executes them where a
client is configured. Blueprint Part 28.2 (l.1203, 1208), Part 9.3, Part 23.3.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICIES = Path(__file__).with_name("policies.yaml")


class WORMViolation(RuntimeError):
    """Raised when an action would expire/shorten an object-lock object early."""


@dataclass
class Action:
    store: str  # clickhouse | object_store | postgres
    target: str  # table / bucket
    op: str  # move | expire | transition | hold | refuse
    after_days: int | None
    tier: str = ""  # cold | archive | ""
    classification: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# policy loading + the WORM safety invariant
# ---------------------------------------------------------------------------
def load_policies(path: str | os.PathLike[str] = DEFAULT_POLICIES) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def check_worm_safe(bucket: str, cfg: dict[str, Any]) -> None:
    """Raise WORMViolation if a locked bucket would expire below its lock period.

    The audit-archive bucket must NEVER set a finite expiry (regulator-grade).
    Any object-lock bucket's expiry must be >= its lock period.
    """
    if not cfg.get("object_lock"):
        return
    lock_days = cfg.get("lock_days")
    expire_days = cfg.get("expire_days")
    expire_noncurrent = cfg.get("expire_noncurrent_days")
    if bucket == "audit-archive" and expire_days is not None:
        raise WORMViolation(
            f"audit-archive must never auto-expire (got expire_days={expire_days})"
        )
    for candidate in (expire_days, expire_noncurrent):
        if candidate is not None and lock_days is not None and candidate < lock_days:
            raise WORMViolation(
                f"{bucket}: expiry {candidate}d < object-lock {lock_days}d — refused"
            )


# ---------------------------------------------------------------------------
# planners (pure; no infra)
# ---------------------------------------------------------------------------
def plan_clickhouse(policies: dict[str, Any]) -> list[Action]:
    out: list[Action] = []
    tables = policies["stores"]["clickhouse"]["tables"]
    for table, cfg in tables.items():
        cls = cfg.get("classification", "operational")
        out.append(
            Action(
                "clickhouse",
                table,
                "move",
                cfg["hot_days"],
                "cold",
                cls,
                f"hot->cold at {cfg['hot_days']}d",
            )
        )
        out.append(
            Action(
                "clickhouse",
                table,
                "move",
                cfg["cold_days"],
                "archive",
                cls,
                f"cold->archive at {cfg['cold_days']}d",
            )
        )
        if cfg.get("expire"):
            out.append(
                Action(
                    "clickhouse",
                    table,
                    "expire",
                    cfg["archive_days"],
                    "",
                    cls,
                    f"DELETE at {cfg['archive_days']}d (operational)",
                )
            )
        else:
            out.append(
                Action(
                    "clickhouse",
                    table,
                    "hold",
                    cfg["archive_days"],
                    "archive",
                    cls,
                    f"evidence: held, no auto-expire ({cfg['archive_days']}d+)",
                )
            )
    return out


def plan_object_store(policies: dict[str, Any]) -> list[Action]:
    out: list[Action] = []
    buckets = policies["stores"]["object_store"]["buckets"]
    for bucket, cfg in buckets.items():
        check_worm_safe(bucket, cfg)  # invariant enforced BEFORE any action
        cls = cfg.get("classification", "operational")
        if cfg.get("transition_archive_days") is not None:
            out.append(
                Action(
                    "object_store",
                    bucket,
                    "transition",
                    cfg["transition_archive_days"],
                    "archive",
                    cls,
                    "lifecycle: transition to archive tier (stays immutable if locked)",
                )
            )
        if cfg.get("object_lock"):
            out.append(
                Action(
                    "object_store",
                    bucket,
                    "hold",
                    cfg.get("lock_days"),
                    "",
                    cls,
                    f"object-lock WORM hold {cfg.get('lock_days')}d (never shortened)",
                )
            )
        if cfg.get("expire_days") is not None:
            out.append(
                Action(
                    "object_store",
                    bucket,
                    "expire",
                    cfg["expire_days"],
                    "",
                    cls,
                    "lifecycle: expire current versions",
                )
            )
        if cfg.get("expire_noncurrent_days") is not None:
            out.append(
                Action(
                    "object_store",
                    bucket,
                    "expire",
                    cfg["expire_noncurrent_days"],
                    "noncurrent",
                    cls,
                    "lifecycle: expire NON-current versions (old model versions, Part 23.3)",
                )
            )
    return out


def plan_postgres(policies: dict[str, Any]) -> list[Action]:
    out: list[Action] = []
    for table, cfg in policies["stores"]["postgres"]["tables"].items():
        cls = cfg.get("classification", "operational")
        retain = cfg.get("retain_days")
        if cfg.get("legal_hold") or retain is None:
            out.append(
                Action(
                    "postgres",
                    table,
                    "hold",
                    None,
                    "",
                    cls,
                    "legal hold / retained per DPDP legal basis",
                )
            )
        else:
            op = "hold" if cfg.get("fraud_carveout") else "expire"
            out.append(
                Action(
                    "postgres",
                    table,
                    op,
                    retain,
                    "",
                    cls,
                    f"archive/export then {op} at {retain}d",
                )
            )
    return out


def build_plan(policies: dict[str, Any]) -> list[Action]:
    return (
        plan_clickhouse(policies)
        + plan_object_store(policies)
        + plan_postgres(policies)
    )


def fraud_carveout_targets(policies: dict[str, Any]) -> dict[str, Any]:
    """The confirmed-fraud carve-out spec (longer hold). Used to verify no expiry
    action ever shortens fraud-linked evidence below the carve-out floor."""
    return policies.get("fraud_carveout", {})


# ---------------------------------------------------------------------------
# appliers (guarded; only run when a client is configured)
# ---------------------------------------------------------------------------
def _split_sql_statements(sql: str) -> list[str]:
    """Split a SQL file into executable statements.

    Strips ``--`` line comments FIRST (a naive split-on-';' then drop-if-startswith-'--'
    silently drops every real statement, because each ALTER is preceded by a comment
    line so the whole chunk 'starts with --'). The remaining DDL has no intra-statement
    ';' (TTL clauses use commas), so splitting the comment-free text on ';' is safe.
    """
    no_comments = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def apply_clickhouse_ttl(ch_client: Any, ttl_sql_path: str | None = None) -> None:
    """Apply the authoritative MODIFY TTL statements (clickhouse_ttl.sql).

    `MODIFY TTL` re-validates the table metadata, so tables carrying a full-text
    (inverted) index — events/alerts/dispositions — require the experimental flag
    in-session or the ALTER fails with SUPPORT_IS_DISABLED (verified live on CH
    25.3). We pass it per statement (clickhouse_connect `settings=`).
    """
    path = ttl_sql_path or str(Path(__file__).with_name("clickhouse_ttl.sql"))
    settings = {"allow_experimental_full_text_index": 1}
    for stmt in _split_sql_statements(Path(path).read_text(encoding="utf-8")):
        try:
            ch_client.command(stmt, settings=settings)
        except TypeError:
            # a client that doesn't accept settings= (e.g. a simple shim)
            ch_client.command(stmt)


def force_move_partition(
    ch_client: Any, table: str, partition: str, volume: str
) -> None:
    """Deterministically move one partition to a volume (demo/integration proof)."""
    ch_client.command(
        f"ALTER TABLE hawkeye.{table} MOVE PARTITION '{partition}' TO VOLUME '{volume}'"
    )


def apply_object_store_lifecycle(minio_client: Any, policies: dict[str, Any]) -> None:
    """Set MinIO bucket lifecycle (transition + expiration), honoring object-lock.

    Re-checks the WORM invariant per bucket before applying.
    """
    from minio.lifecycleconfig import Expiration, LifecycleConfig, Rule, Transition  # type: ignore

    buckets = policies["stores"]["object_store"]["buckets"]
    for bucket, cfg in buckets.items():
        check_worm_safe(bucket, cfg)
        rules: list[Any] = []
        if cfg.get("transition_archive_days") is not None:
            rules.append(
                Rule(
                    rule_id=f"{bucket}-to-archive",
                    status="Enabled",
                    transition=Transition(
                        days=cfg["transition_archive_days"], storage_class="GLACIER"
                    ),
                )
            )
        if cfg.get("expire_days") is not None:
            rules.append(
                Rule(
                    rule_id=f"{bucket}-expire",
                    status="Enabled",
                    expiration=Expiration(days=cfg["expire_days"]),
                )
            )
        if rules:
            minio_client.set_bucket_lifecycle(bucket, LifecycleConfig(rules))


def run(
    apply: bool = False, policies_path: str | os.PathLike[str] = DEFAULT_POLICIES
) -> list[Action]:
    policies = load_policies(policies_path)
    plan = build_plan(policies)  # raises WORMViolation if a policy is unsafe
    for a in plan:
        flag = "APPLY" if apply else "PLAN"
        print(
            f"[{flag}] {a.store:13s} {a.target:18s} {a.op:10s} "
            f"after={a.after_days} tier={a.tier or '-':8s} [{a.classification}] {a.reason}"
        )
    if apply:
        _apply_all(policies)
    return plan


def _apply_all(policies: dict[str, Any]) -> None:  # pragma: no cover - infra path
    # ClickHouse
    try:
        import clickhouse_connect

        ch = clickhouse_connect.get_client(
            host=os.getenv("CH_HOST", "localhost"),
            port=int(os.getenv("CH_HTTP_PORT", "8123")),
            username=os.getenv("CH_USER", "hawkeye"),
            password=os.getenv("CH_PASSWORD", "hawkeye_dev_pw"),
        )
        apply_clickhouse_ttl(ch)
        print("[APPLY] ClickHouse TTL applied")
    except Exception as exc:
        print(f"[APPLY] ClickHouse skipped: {exc}")
    # MinIO
    try:
        from minio import Minio

        m = Minio(
            os.getenv("MINIO_ENDPOINT", "localhost:9001"),
            access_key=os.getenv("MINIO_ROOT_USER", "hawkeye"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "hawkeye_dev_pw"),
            secure=False,
        )
        apply_object_store_lifecycle(m, policies)
        print("[APPLY] MinIO lifecycle applied")
    except Exception as exc:
        print(f"[APPLY] MinIO skipped: {exc}")


def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="Hawk-Eye retention/archival job (DATABASE-9)"
    )
    ap.add_argument("--apply", action="store_true", help="apply (default = plan only)")
    ap.add_argument("--policies", default=str(DEFAULT_POLICIES))
    ap.add_argument("--json", action="store_true", help="emit the plan as JSON")
    args = ap.parse_args()
    try:
        plan = run(apply=args.apply, policies_path=args.policies)
    except WORMViolation as exc:
        print(f"REFUSED (WORM invariant): {exc}")
        return 3
    if args.json:
        import json

        print(json.dumps([asdict(a) for a in plan], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
