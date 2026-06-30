"""Feature repo: single train/serve feature definition (DATA-6).

Blueprint Part 8 (Feast + Redis online feature store, l.301), Part 6 engineering note
(l.259): compute in Flink, materialize in Feast/Redis online, backfill the SAME
definitions in ClickHouse offline so training and serving use identical logic.

Status: REAL on pure-python; Feast is OPTIONAL. When Feast (0.40.x) is installed the
same Entity/FeatureView definitions can be exported to Feast objects (see
``to_feast_objects``); without it the pure-python ``FeatureRepo`` provides the offline
(get_historical_features) and the online path drives ``OnlineStore`` — the parity
contract holds either way because there is exactly ONE definition.

This module demonstrates ONE entity (employee) + one feature view; DATA-20/21 add the
full catalogue against the same machinery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import pandas as pd

# ---- optional Feast (single definition reused if present) -------------------
try:  # pragma: no cover - exercised only when feast present
    import feast  # type: ignore  # noqa: F401

    _HAVE_FEAST = True
except Exception:  # pragma: no cover
    feast = None  # type: ignore
    _HAVE_FEAST = False


@dataclass(frozen=True)
class Entity:
    """An entity keyed by a join column (e.g. employee_id)."""

    name: str
    join_key: str
    description: str = ""


@dataclass(frozen=True)
class Feature:
    """A single feature: name + dtype + the offline column it reads from."""

    name: str
    dtype: str
    source_column: str
    description: str = ""


@dataclass(frozen=True)
class FeatureView:
    """A named group of features for one entity. The SINGLE definition used by both
    the offline retrieval and the online serving paths."""

    name: str
    entity: Entity
    features: tuple[Feature, ...]
    ttl_seconds: int = 3600

    @property
    def feature_names(self) -> list[str]:
        return [f.name for f in self.features]


# ---- the demonstrated employee entity + one feature view --------------------
EMPLOYEE = Entity(
    name="employee",
    join_key="employee_id",
    description="One employee identity (EMP-*); the primary insider entity.",
)

EMPLOYEE_RISK_VIEW = FeatureView(
    name="employee_risk",
    entity=EMPLOYEE,
    features=(
        Feature("offhours_event_count_30d", "int64", "offhours_event_count_30d",
                "Count of off-hours events in the trailing 30 days."),
        Feature("txn_amount_zscore", "float64", "txn_amount_zscore",
                "Amount z-score vs the employee's own history."),
        Feature("new_beneficiary_count_7d", "int64", "new_beneficiary_count_7d",
                "New beneficiaries created in the trailing 7 days."),
    ),
    ttl_seconds=3600,
)


@dataclass
class FeatureRepo:
    """Pure-python feature repo holding entities + feature views (the registry).

    ``apply()`` registers definitions (Feast-`apply` analogue). ``get_historical_features``
    is the OFFLINE path; ``materialize`` pushes the latest row per entity into the
    OnlineStore for the ONLINE path. Both read the SAME FeatureView, guaranteeing parity.
    """

    entities: dict[str, Entity] = field(default_factory=dict)
    feature_views: dict[str, FeatureView] = field(default_factory=dict)

    def apply(self, *objs: Any) -> "FeatureRepo":
        for obj in objs:
            if isinstance(obj, Entity):
                self.entities[obj.name] = obj
            elif isinstance(obj, FeatureView):
                self.feature_views[obj.name] = obj
                self.entities[obj.entity.name] = obj.entity
            else:
                raise TypeError(f"cannot apply object of type {type(obj)!r}")
        return self

    def get_view(self, name: str) -> FeatureView:
        return self.feature_views[name]

    def get_historical_features(
        self, entity_df: pd.DataFrame, view_name: str
    ) -> pd.DataFrame:
        """OFFLINE retrieval: join requested feature columns onto an entity frame.

        ``entity_df`` must contain the entity join key. This mirrors Feast's
        ``get_historical_features`` and uses the SAME FeatureView definition that the
        online path uses — the parity contract.
        """
        view = self.feature_views[view_name]
        join_key = view.entity.join_key
        if join_key not in entity_df.columns:
            raise KeyError(f"entity_df missing join key '{join_key}'")
        wanted = [f.name for f in view.features]
        # source columns may differ from feature names; build a rename map
        rename = {f.source_column: f.name for f in view.features}
        present = [c for c in entity_df.columns if c in rename or c in wanted]
        out = entity_df.copy()
        out = out.rename(columns={c: rename[c] for c in present if c in rename})
        keep = [join_key] + [c for c in wanted if c in out.columns]
        return out[keep]

    def materialize(
        self, feature_df: pd.DataFrame, view_name: str, store: "OnlineStoreProto"
    ) -> int:
        """Push the latest feature row per entity into the online store (ONLINE path).

        Returns the number of entities written. Uses the SAME FeatureView definition.
        """
        view = self.feature_views[view_name]
        join_key = view.entity.join_key
        rename = {f.source_column: f.name for f in view.features}
        df = feature_df.rename(columns=rename)
        written = 0
        for _, row in df.iterrows():
            key = str(row[join_key])
            values = {
                f.name: row[f.name]
                for f in view.features
                if f.name in df.columns and pd.notna(row.get(f.name))
            }
            store.write(view.entity.name, key, values, ttl_seconds=view.ttl_seconds)
            written += 1
        return written

    # -- optional Feast bridge -------------------------------------------------
    def to_feast_objects(self) -> Optional[list[Any]]:  # pragma: no cover - opt dep
        """If Feast is installed, build equivalent Feast Entity/FeatureView objects from
        the SAME definitions. Returns None when Feast is absent (pure-python fallback)."""
        if not _HAVE_FEAST:
            return None
        from datetime import timedelta

        from feast import Entity as FEntity  # type: ignore
        from feast import Feature as FFeature  # type: ignore
        from feast import FeatureView as FFeatureView  # type: ignore
        from feast import ValueType  # type: ignore

        objs: list[Any] = []
        for ent in self.entities.values():
            objs.append(FEntity(name=ent.name, join_keys=[ent.join_key]))
        for view in self.feature_views.values():
            objs.append(
                FFeatureView(
                    name=view.name,
                    entities=[view.entity.name],
                    ttl=timedelta(seconds=view.ttl_seconds),
                    schema=[FFeature(name=f.name, dtype=ValueType.DOUBLE)
                            for f in view.features],
                )
            )
        return objs


# Structural protocol for the online store (avoids importing it at module top for
# the type only).
class OnlineStoreProto:  # pragma: no cover - typing aid
    def write(self, entity: str, key: str, values: dict[str, Any],
              ttl_seconds: int = 3600) -> None: ...


def build_repo() -> FeatureRepo:
    """Tiny demo helper: build a repo with the employee entity + risk view applied."""
    return FeatureRepo().apply(EMPLOYEE, EMPLOYEE_RISK_VIEW)
