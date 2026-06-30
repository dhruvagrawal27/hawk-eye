"""Rule definition loader + hot-reload (BACKEND-5, blueprint Part 20.1 'hot-reloadable + versioned').

Loads ``rules_engine/rules/*.yaml`` into ``RuleConfig`` objects. ``load()`` returns the configs and
a content fingerprint; the engine calls ``maybe_reload()`` which re-reads only when a file changed
(mtime + size), so a four-eyes rule change (BACKEND-8) takes effect without a restart.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from rules_engine.rule import RuleConfig

RULES_DIR = Path(__file__).parent / "rules"
_SOD_FILE = "sod_matrix.yaml"


def _coerce(entry: dict) -> RuleConfig:
    return RuleConfig(
        code=entry["code"],
        name=entry.get("name", entry["code"]),
        enabled=bool(entry.get("enabled", True)),
        severity=entry.get("severity", "medium"),
        hard_hit=bool(entry.get("hard_hit", False)),
        version=str(entry.get("version", "1.0.0")),
        description=entry.get("description", ""),
        params=dict(entry.get("params", {}) or {}),
    )


def fingerprint(rules_dir: Path = RULES_DIR) -> tuple:
    """Cheap change-detection fingerprint over the rule files (excludes the SoD matrix)."""
    stamps = []
    for path in sorted(rules_dir.glob("*.yaml")):
        if path.name == _SOD_FILE:
            continue
        st = path.stat()
        stamps.append((path.name, int(st.st_mtime_ns), st.st_size))
    return tuple(stamps)


def load(rules_dir: Path = RULES_DIR) -> dict[str, RuleConfig]:
    """Load every rule config keyed by code (last definition wins on duplicate codes)."""
    configs: dict[str, RuleConfig] = {}
    if not rules_dir.exists():
        return configs
    # Load the aggregate ``rules.yaml`` FIRST, then per-code files so a four-eyes change persisted to
    # ``<code>.yaml`` overrides the base definition (last write wins).
    paths = sorted(rules_dir.glob("*.yaml"), key=lambda p: (p.name != "rules.yaml", p.name))
    for path in paths:
        if path.name == _SOD_FILE:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries = data.get("rules") if isinstance(data, dict) and "rules" in data else [data]
        for entry in entries:
            if not entry or "code" not in entry:
                continue
            cfg = _coerce(entry)
            configs[cfg.code] = cfg
    return configs


def load_sod_conflicts(rules_dir: Path = RULES_DIR) -> list[frozenset[str]]:
    """Load the configurable SoD conflict matrix (BACKEND-6)."""
    path = rules_dir / _SOD_FILE
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[frozenset[str]] = []
    for pair in data.get("conflicts", []):
        items = {str(x).lower() for x in pair}
        if len(items) >= 2:
            out.append(frozenset(items))
    return out


def write_rule(cfg: RuleConfig, rules_dir: Path = RULES_DIR) -> None:
    """Persist a (changed) rule back to its own file — used by the four-eyes CRUD on approval.

    Writes to ``<code>.yaml`` (lower-cased) so changes are diff-friendly and the original
    ``rules.yaml`` aggregate is overridden by the per-code file on next load.
    """
    rules_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "code": cfg.code,
        "name": cfg.name,
        "enabled": cfg.enabled,
        "severity": cfg.severity,
        "hard_hit": cfg.hard_hit,
        "version": cfg.version,
        "description": cfg.description,
        "params": cfg.params,
    }
    out = rules_dir / f"{cfg.code.lower()}.yaml"
    tmp = out.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    os.replace(tmp, out)  # atomic
