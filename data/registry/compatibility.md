# L0 Schema Registry — Compatibility Policy (DATA-2)

**Blueprint:** Part 28.2 (schema registry & evolution, l.1206), Part 32.1 (event-schema
governance, l.1302). **Status:** REAL (policy enforced by
`data/registry/schema_registry.py`); PLATFORM hosts the registry runtime (seam 5.7) —
DATA owns the *content & compatibility policy*.

## Subject

| Subject | Schema | Owner |
|---|---|---|
| `events.raw-value` | L0 `AVRO_SCHEMA` (`data/schemas/l0_event.py`) | DATA (BACKEND consumes) |

## Compatibility mode: **BACKWARD**

We pin **BACKWARD** compatibility (optionally `BACKWARD_TRANSITIVE` across all prior
versions). BACKWARD means: **a consumer using the *new* schema can read data written
with the *old* schema.** This is the safety property we need — a source-system upgrade
(e.g. a CBS / Finacle field change) that registers a new schema version must never
silently break the downstream features, rules and models that already consume
`events.raw`.

### Allowed (compatible) evolutions

- **Add a new OPTIONAL field** — a union with `null` and a `default` (e.g.
  `["null", "string"]`, `default: null`). Old data simply has no value for it; new
  consumers see the default. This is the additive change the registry **accepts**.
- Widen a numeric default, add documentation, reorder is irrelevant (Avro is
  name-based).

### Rejected (breaking) evolutions

- **Removing a field** that exists in the current version.
- **Renaming a field** — Avro matches by name, so a rename looks like *remove old name +
  add new name* and is rejected as a removal.
- **Adding a REQUIRED field** (no default) — old data would have no value for it.
- **Making an optional field required**, or an incompatible **base-type change**.

These map directly to the negative test in `data/tests/test_governance.py`:
removing/renaming `actor.employee_id`-style required fields is rejected; adding an
optional field (e.g. `context.tz`) is accepted.

## Enforcement

`SchemaRegistry.register(subject, schema)` calls `is_compatible(latest, new)` before
accepting a new version and raises `ValueError` on an incompatible change. The decision
rule is pure-python (numpy/pandas-free); if `fastavro` is installed it is additionally
used to confirm both schemas parse as valid Avro, but the compatibility *verdict* is
ours so behaviour is identical with or without the optional dependency.

## Coordination

Any field add/rename to L0 is a **contract change**: propose it in `CONTEXT.md` tagged
`[BACKEND]` (BACKEND mirrors `BACKEND.md` §1), then register the new optional field here.
