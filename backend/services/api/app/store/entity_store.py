"""Entity-360 store (BACKEND-19).

# STUB: DATABASE (ClickHouse timeline/graph queries) + ML (graph/peers). Holds per-entity profile,
unified timeline, relationship subgraph, and peer comparisons. Seeded synthetically by
``store.seed`` (the worked-burst entity EMP-7f3a + peers). All identifiers are tokenized.
"""

from __future__ import annotations

from app.schemas.entities import (
    EntityGraph,
    EntityProfile,
    PeerComparison,
    TimelineEvent,
)


class EntityStore:
    def __init__(self) -> None:
        self._profiles: dict[str, EntityProfile] = {}
        self._timelines: dict[str, list[TimelineEvent]] = {}
        self._graphs: dict[str, EntityGraph] = {}
        self._peers: dict[str, list[PeerComparison]] = {}

    def put_profile(self, profile: EntityProfile) -> None:
        self._profiles[profile.entity_id] = profile

    def put_timeline(self, entity_id: str, events: list[TimelineEvent]) -> None:
        self._timelines[entity_id] = events

    def put_graph(self, graph: EntityGraph) -> None:
        self._graphs[graph.entity_id] = graph

    def put_peers(self, entity_id: str, peers: list[PeerComparison]) -> None:
        self._peers[entity_id] = peers

    def get_profile(self, entity_id: str) -> EntityProfile | None:
        return self._profiles.get(entity_id)

    def get_timeline(self, entity_id: str) -> list[TimelineEvent]:
        return self._timelines.get(entity_id, [])

    def get_graph(self, entity_id: str) -> EntityGraph | None:
        return self._graphs.get(entity_id)

    def get_peers(self, entity_id: str) -> list[PeerComparison]:
        return self._peers.get(entity_id, [])


ENTITIES = EntityStore()
