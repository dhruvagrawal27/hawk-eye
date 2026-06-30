"""Schema registry, versioning & evolution governance (DATA-2).

Blueprint Part 28.2 (l.1206 — schema registry & evolution) and Part 32.1 (l.1302 —
event-schema governance so a CBS upgrade can't silently break features).

Status: REAL (runs on the in-repo Avro schema; fastavro / jsonschema are OPTIONAL).

What this provides:
  - A pure-python SchemaRegistry that registers the L0 ``AVRO_SCHEMA`` under a subject
    with monotonically increasing versions.
  - Compatibility policy = BACKWARD (a new schema can read data written with the old
    schema): you may ADD optional fields (with defaults) and you may NOT remove or
    rename a required field. ``is_compatible(old, new)`` enforces exactly this.
  - When fastavro is installed we additionally parse both schemas to confirm they are
    well-formed Avro; without it we fall back to a structural check. Either way the
    compatibility *decision* is made by our own pure-python rule so behaviour is
    identical with or without the optional dependency.

See ``data/registry/compatibility.md`` for the documented policy.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

from data.schemas import AVRO_SCHEMA

# ---- optional fastavro (only used to validate the schema is parseable) -------
try:  # pragma: no cover - exercised only when fastavro present
    import fastavro  # type: ignore

    _HAVE_FASTAVRO = True
except Exception:  # pragma: no cover
    fastavro = None  # type: ignore
    _HAVE_FASTAVRO = False


class Compatibility:
    """Compatibility modes (Confluent/Apicurio-compatible vocabulary)."""

    NONE = "NONE"
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    FULL = "FULL"
    BACKWARD_TRANSITIVE = "BACKWARD_TRANSITIVE"


# Default policy for the L0 event subject (blueprint Part 28.2 / engineering note in
# prompts/01_DATA.md M1: compatibility = BACKWARD so source-system upgrades are safe).
DEFAULT_COMPATIBILITY = Compatibility.BACKWARD


def _avro_field_index(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map field-name -> field-definition for a top-level Avro record."""
    out: dict[str, dict[str, Any]] = {}
    for f in schema.get("fields", []):
        out[f["name"]] = f
    return out


def _is_optional(field_def: dict[str, Any]) -> bool:
    """A field is 'optional' (safe to add under BACKWARD) iff it has a default,
    which in Avro means a union starting with ``null`` and ``default: null`` or any
    explicit default value."""
    if "default" in field_def:
        return True
    t = field_def.get("type")
    if isinstance(t, list) and "null" in t:
        return True
    return False


def _validate_parseable(schema: dict[str, Any]) -> list[str]:
    """If fastavro is present, confirm the schema parses; else a light structural check."""
    errors: list[str] = []
    if _HAVE_FASTAVRO:  # pragma: no cover - depends on optional dep
        try:
            fastavro.parse_schema(copy.deepcopy(schema))  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover
            errors.append(f"avro parse error: {exc}")
        return errors
    # Pure-python fallback structural validation.
    if schema.get("type") != "record":
        errors.append("top-level schema must be an Avro record")
    if "name" not in schema:
        errors.append("record missing 'name'")
    if not isinstance(schema.get("fields"), list):
        errors.append("record missing 'fields' list")
    return errors


def is_compatible(old: dict[str, Any], new: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return (compatible, reasons) under the BACKWARD policy.

    BACKWARD = a consumer using ``new`` can read data written with ``old``. Breaking
    changes we reject:
      * removing a field that exists in ``old`` (a renamed field looks like a removal
        of the old name + addition of the new name -> rejected).
      * making a previously-optional field required, or adding a *required* field
        (no default) in ``new`` (old data would have no value for it).
      * changing a field's base type incompatibly.
    Accepted: adding a new OPTIONAL field (union with null / has default).
    """
    reasons: list[str] = []

    parse_errs = _validate_parseable(old) + _validate_parseable(new)
    if parse_errs:
        return False, parse_errs

    old_fields = _avro_field_index(old)
    new_fields = _avro_field_index(new)

    # 1. No field present in old may disappear from new (covers removal AND rename).
    for name in old_fields:
        if name not in new_fields:
            reasons.append(
                f"breaking: required/known field '{name}' removed or renamed "
                f"(BACKWARD-incompatible)"
            )

    # 2. New fields must be optional (have a default) so old data stays readable.
    for name, fdef in new_fields.items():
        if name not in old_fields and not _is_optional(fdef):
            reasons.append(
                f"breaking: new field '{name}' added without a default "
                f"(BACKWARD-incompatible)"
            )

    # 3. A field that existed must not become required if it was optional, and its
    #    base type must not change incompatibly.
    for name, old_def in old_fields.items():
        if name not in new_fields:
            continue
        new_def = new_fields[name]
        if _is_optional(old_def) and not _is_optional(new_def):
            reasons.append(
                f"breaking: field '{name}' changed from optional to required"
            )
        if _base_type(old_def) != _base_type(new_def):
            reasons.append(
                f"breaking: field '{name}' base type changed "
                f"{_base_type(old_def)} -> {_base_type(new_def)}"
            )

    return (len(reasons) == 0), reasons


def _base_type(field_def: dict[str, Any]) -> str:
    """Coarse base-type signature for a field, ignoring null-ability for the comparison
    of 'is this still the same kind of value'."""
    t = field_def.get("type")
    if isinstance(t, list):
        non_null = [x for x in t if x != "null"]
        t = non_null[0] if non_null else "null"
    if isinstance(t, dict):
        return str(t.get("type", "record"))
    return str(t)


@dataclass
class _RegisteredVersion:
    version: int
    schema: dict[str, Any]


@dataclass
class SchemaRegistry:
    """In-process schema registry (SCAFFOLD-compatible with Confluent/Apicurio).

    PLATFORM hosts the real registry runtime (seam 5.7); this pure-python registry runs
    the *content & compatibility policy* locally so DATA tests and the simulator do not
    need a live registry. Swapping in a real registry is a client-config change.
    """

    compatibility: str = DEFAULT_COMPATIBILITY
    _subjects: dict[str, list[_RegisteredVersion]] = field(default_factory=dict)

    def register(self, subject: str, schema: dict[str, Any]) -> int:
        """Register ``schema`` under ``subject`` if compatible with the latest version.

        Returns the assigned version number. Raises ValueError on an incompatible
        evolution (the negative-test path required by DATA-2).
        """
        versions = self._subjects.get(subject, [])
        if versions and self.compatibility != Compatibility.NONE:
            latest = versions[-1].schema
            ok, reasons = is_compatible(latest, schema)
            if not ok:
                raise ValueError(
                    f"schema for subject '{subject}' is "
                    f"{self.compatibility}-incompatible: {reasons}"
                )
        new_version = (versions[-1].version + 1) if versions else 1
        versions.append(_RegisteredVersion(new_version, copy.deepcopy(schema)))
        self._subjects[subject] = versions
        return new_version

    def latest(self, subject: str) -> Optional[dict[str, Any]]:
        versions = self._subjects.get(subject)
        return copy.deepcopy(versions[-1].schema) if versions else None

    def versions(self, subject: str) -> list[int]:
        return [v.version for v in self._subjects.get(subject, [])]


L0_SUBJECT = "events.raw-value"


def register_l0(registry: Optional[SchemaRegistry] = None) -> SchemaRegistry:
    """Register the canonical L0 ``AVRO_SCHEMA`` under the events.raw subject."""
    registry = registry or SchemaRegistry(compatibility=Compatibility.BACKWARD)
    registry.register(L0_SUBJECT, AVRO_SCHEMA)
    return registry


def _demo() -> SchemaRegistry:
    """Tiny demo helper used by tests: register L0 and return the registry."""
    return register_l0()
