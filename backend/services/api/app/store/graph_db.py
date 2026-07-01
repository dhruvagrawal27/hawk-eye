"""Neo4j graph-database seam for L5 relational detection.

The L5 entity graph (collusion rings, maker-checker subgraphs, shared-resource links) runs in-process
by default. When HAWKEYE_NEO4J_ENABLED + the neo4j driver is importable + bolt is reachable, this seam
exposes a live ping/query against a persistent graph so the same relationships can be stored/queried
at scale. Guarded — scoring never depends on it. Surfaced on the Service Map (key 'neo4j').
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings

log = logging.getLogger("hawkeye.graph_db")


class GraphDB:
    def __init__(self) -> None:
        self._driver = None
        if settings.neo4j_enabled:
            self._driver = self._connect()

    def _connect(self):
        try:
            from neo4j import GraphDatabase  # type: ignore

            driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=2.0,
            )
            driver.verify_connectivity()
            log.info("neo4j graph db active at %s", settings.neo4j_uri)
            return driver
        except Exception as exc:  # noqa: BLE001 - unavailable → in-process graph stays the default
            log.warning("neo4j disabled (%s); L5 graph runs in-process", exc)
            return None

    @property
    def is_active(self) -> bool:
        return self._driver is not None

    def ping(self) -> bool:
        if self._driver is None:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:  # noqa: BLE001
            return False

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """Run a read query; returns rows as dicts. Empty list when Neo4j is not active."""
        if self._driver is None:
            return []
        try:
            with self._driver.session() as session:
                return [dict(r) for r in session.run(cypher, **params)]
        except Exception:  # noqa: BLE001
            return []

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass


GRAPH_DB = GraphDB()
