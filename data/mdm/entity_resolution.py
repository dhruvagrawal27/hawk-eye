"""MDM / entity resolution: one identity across CBS/HR/IAM (DATA-26).

Blueprint Part 28.2 (l.1207): "consistent entity resolution (one employee, one customer
identity) across CBS/HR/IAM — essential for the entity-360 and graph layers." Status:
REAL.

Approach: deterministic matching on shared keys. Each source system emits a
``SourceRecord`` with a local id and a set of match keys (employee_id, email,
national_id_token, customer_account...). Records are merged into one ``ResolvedEntity``
when they share at least one strong key — a union-find over the records groups all
transitively-linked records into a single golden identity. The resolver is deterministic
and synthetic-only (tokenized ids; no real PII).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from data.config import make_id

# Keys strong enough to assert "same person/entity" when shared across sources.
STRONG_KEYS = ("employee_id", "national_id_token", "email", "customer_account")


@dataclass(frozen=True)
class SourceRecord:
    """A record about an entity from one source system (CBS / HR / IAM)."""

    source: str                 # "cbs" | "hr" | "iam"
    local_id: str               # the id within that source system
    keys: dict[str, str] = field(default_factory=dict)  # shared match keys

    def strong_pairs(self) -> set[tuple[str, str]]:
        """The (key_name, value) pairs usable for matching."""
        return {
            (k, v) for k, v in self.keys.items()
            if k in STRONG_KEYS and v
        }


@dataclass
class ResolvedEntity:
    """A golden identity merging records from multiple sources."""

    entity_id: str
    records: list[SourceRecord] = field(default_factory=list)

    @property
    def sources(self) -> set[str]:
        return {r.source for r in self.records}

    @property
    def keys(self) -> dict[str, set[str]]:
        agg: dict[str, set[str]] = {}
        for r in self.records:
            for k, v in r.keys.items():
                agg.setdefault(k, set()).add(v)
        return agg

    def source_ids(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for r in self.records:
            out.setdefault(r.source, []).append(r.local_id)
        return out


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


@dataclass
class EntityResolver:
    """Deterministic entity resolver over source records (union-find on shared keys)."""

    def resolve(self, records: list[SourceRecord]) -> list[ResolvedEntity]:
        if not records:
            return []
        uf = _UnionFind(len(records))
        # Map each strong (key,value) pair to the record indices that carry it; union them.
        pair_to_idx: dict[tuple[str, str], list[int]] = {}
        for i, rec in enumerate(records):
            for pair in rec.strong_pairs():
                pair_to_idx.setdefault(pair, []).append(i)
        for idxs in pair_to_idx.values():
            for j in idxs[1:]:
                uf.union(idxs[0], j)

        groups: dict[int, list[SourceRecord]] = {}
        for i, rec in enumerate(records):
            groups.setdefault(uf.find(i), []).append(rec)

        resolved: list[ResolvedEntity] = []
        for members in groups.values():
            # Deterministic golden id from the sorted strong-key fingerprint.
            fingerprint = sorted(
                f"{k}={v}" for m in members for (k, v) in m.strong_pairs()
            )
            ent_id = make_id("employee", *fingerprint) if fingerprint else \
                make_id("employee", members[0].source, members[0].local_id)
            resolved.append(ResolvedEntity(entity_id=ent_id, records=list(members)))
        # Stable ordering by entity_id for determinism.
        return sorted(resolved, key=lambda e: e.entity_id)


def resolve(records: Iterable[SourceRecord]) -> list[ResolvedEntity]:
    """Module-level convenience: resolve an iterable of source records."""
    return EntityResolver().resolve(list(records))


def _demo_records() -> list[SourceRecord]:
    """Tiny demo: the same person in HR and IAM (shared employee_id) + a CBS link via
    national_id_token, plus an unrelated person."""
    return [
        SourceRecord("hr", "HR-1001", {"employee_id": "EMP-7f3a",
                                        "national_id_token": "NID-abc"}),
        SourceRecord("iam", "iam-jdoe", {"employee_id": "EMP-7f3a",
                                          "email": "jdoe@bank.local"}),
        SourceRecord("cbs", "cbs-55", {"national_id_token": "NID-abc",
                                        "customer_account": "ACCT-4d22"}),
        SourceRecord("hr", "HR-2002", {"employee_id": "EMP-1a09"}),
    ]
