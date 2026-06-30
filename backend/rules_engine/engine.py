"""L1 Rules / Business-Rules Engine (BACKEND-5, blueprint Part 3.1 / 20.1).

The deterministic, necessary-but-insufficient Layer 1. Evaluates an L0 event (+ online features)
against every enabled named rule and the SoD/toxic-combination matrix, returns the fired hits as
``reason_codes``, and signals a **hard hit** for the L1 short-circuit (BACKEND-11). Versioned and
hot-reloadable; works at cold start (no labels). Pure: no ML, no DB, no network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rules_engine.context import RuleContext
from rules_engine.loader import RULES_DIR, fingerprint, load, load_sod_conflicts, write_rule
from rules_engine.named_rules import NAMED_RULES, Predicate
from rules_engine.privileged import PRIVILEGED_RULES
from rules_engine.rule import RuleConfig, RuleHit
from rules_engine.sod_matrix import SoDMatrix, SoDResult

_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
_HARD_SOD_THRESHOLD = 0.9


@dataclass
class EvalResult:
    """Outcome of an L1 evaluation."""

    hits: list[RuleHit] = field(default_factory=list)
    sod: SoDResult = field(default_factory=SoDResult)
    l1_score: float = 0.0
    hard_hit: bool = False
    severity: str = "low"

    @property
    def fired(self) -> bool:
        return bool(self.hits) or self.sod.fired

    @property
    def fired_codes(self) -> list[str]:
        return [h.code for h in self.hits] + [f.code for f in self.sod.flags]

    @property
    def reason_codes(self) -> list[dict]:
        return [h.to_reason_code() for h in self.hits] + [
            f.to_reason_code() for f in self.sod.flags
        ]


class RulesEngine:
    def __init__(self, rules_dir: Path = RULES_DIR, auto_reload: bool = True):
        self._rules_dir = rules_dir
        self._auto_reload = auto_reload
        self._predicates: dict[str, Predicate] = {**NAMED_RULES, **PRIVILEGED_RULES}
        self._configs: dict[str, RuleConfig] = {}
        self._fp: tuple = ()
        self.sod = SoDMatrix()
        self.reload()

    # --- lifecycle / hot reload ---
    def reload(self) -> None:
        self._configs = load(self._rules_dir)
        conflicts = load_sod_conflicts(self._rules_dir)
        self.sod = SoDMatrix(conflicts or None)
        self._fp = fingerprint(self._rules_dir)

    def maybe_reload(self) -> bool:
        """Reload if any rule file changed on disk (cheap mtime/size check). Returns True if reloaded."""
        if not self._auto_reload:
            return False
        current = fingerprint(self._rules_dir)
        if current != self._fp:
            self.reload()
            return True
        return False

    # --- introspection / CRUD (used by BACKEND-8) ---
    def list_rules(self) -> list[RuleConfig]:
        return list(self._configs.values())

    def get_rule(self, code: str) -> RuleConfig | None:
        return self._configs.get(code)

    def known_codes(self) -> set[str]:
        return set(self._predicates) | set(self._configs)

    def upsert_rule(self, cfg: RuleConfig, *, persist: bool = True) -> RuleConfig:
        """Apply a (four-eyes approved) rule change in-memory and optionally persist to YAML."""
        self._configs[cfg.code] = cfg
        if persist:
            write_rule(cfg, self._rules_dir)
            self._fp = fingerprint(self._rules_dir)
        return cfg

    # --- evaluation ---
    def evaluate(self, event: dict, features: dict | None = None) -> EvalResult:
        self.maybe_reload()
        ctx = RuleContext(event=event, features=features or {})
        hits: list[RuleHit] = []
        for code, cfg in self._configs.items():
            if not cfg.enabled:
                continue
            predicate = self._predicates.get(code)
            if predicate is None:
                # A config without a bound predicate is a custom/declarative rule placeholder.
                continue
            hit = predicate(ctx, cfg)
            if hit is not None:
                hits.append(hit)
        sod = self.sod.score(ctx)

        scores = [h.score for h in hits] + ([sod.score] if sod.fired else [])
        l1_score = max(scores) if scores else 0.0
        hard = any(h.hard_hit for h in hits) or sod.score >= _HARD_SOD_THRESHOLD

        severity = "low"
        for h in hits:
            if _SEVERITY_RANK.get(h.severity, 0) > _SEVERITY_RANK.get(severity, 0):
                severity = h.severity
        if sod.fired and _SEVERITY_RANK["high"] > _SEVERITY_RANK.get(severity, 0):
            severity = "high"

        return EvalResult(hits=hits, sod=sod, l1_score=l1_score, hard_hit=hard, severity=severity)


# A process-wide default engine for the API and online path.
DEFAULT_ENGINE = RulesEngine()
