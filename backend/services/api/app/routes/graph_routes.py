"""Cross-entity graph overview (BACKEND; blueprint Part 11 graph console).

GET /graph — the *global* link-analysis subgraph powering the frontend Graph Explorer, as opposed to
GET /entities/{id}/graph which is centred on one entity. It seeds from the top-risk alerts and links
the actors to the systems/entities they share (beneficiaries, accounts, mule rings, devices,
maker-checker counterparties), which it extracts from each alert's tokenized reason-code evidence.
When two actors touch the same beneficiary or ring, they connect through that shared node — the
cross-entity signal the page exists to surface.

Read-only. Emits the frontend GraphOverviewResponse shape (nodes/edges use ``type``, plus
``is_focus``/``collusion``/``amount_inr``), which intentionally differs from the entity-scoped
EntityGraph model (which uses ``kind``).
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.audit.writer import AUDIT
from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.schemas.common import Capability
from app.store.alert_store import ALERTS

router = APIRouter(tags=["graph"])


class OverviewNode(BaseModel):
    id: str
    type: str  # employee | beneficiary | account | device | ip | system  (frontend GraphNodeType)
    label: str
    risk: int | None = None
    is_focus: bool = False
    tokenized: bool = True


class OverviewEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str  # transaction | beneficiary | mule | shared_device | maker_checker  (GraphEdgeType)
    label: str | None = None
    weight: float = 1.0
    collusion: bool = False
    amount_inr: int | None = None


class GraphOverview(BaseModel):
    entity_id: str = "overview"  # synthetic marker (not a focus entity) per the FE contract
    nodes: list[OverviewNode] = Field(default_factory=list)
    edges: list[OverviewEdge] = Field(default_factory=list)
    min_score: int = 0


# Tokenized entities that appear in reason-code details -> (node type, edge type, pattern).
# Ordered; each match becomes a shared node the seed actor links to.
_TOKEN_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("beneficiary", "transaction", re.compile(r"\bBEN-[0-9A-Za-z]+\b")),
    ("account", "transaction", re.compile(r"\bACCT-[0-9A-Za-z]+\b")),
    ("system", "mule", re.compile(r"\bRNG-[0-9A-Za-z]+\b")),
    ("device", "shared_device", re.compile(r"\b(?:WS|DEV)-[0-9A-Za-z]+\b")),
]
_EMP_RE = re.compile(r"\bEMP-[0-9A-Za-z]+\b")
_AMOUNT_RE = re.compile(r"INR\s*([0-9,]+)")


@router.get("/graph", response_model=GraphOverview)
def get_graph_overview(
    min_score: int = Query(0, ge=0, le=100, description="Risk floor for seed actors"),
    limit: int = Query(14, ge=1, le=100, description="Max seed actors (top-risk)"),
    principal: Principal = Depends(require_capability(Capability.VIEW_ALERTS)),
) -> GraphOverview:
    # Alerts are one-per-actor; rank by risk, apply the floor, keep the top `limit` as seed actors.
    ranked = sorted(ALERTS.all(), key=lambda a: a.risk_score, reverse=True)
    seeds = [a for a in ranked if a.risk_score >= min_score][:limit]

    nodes: dict[str, OverviewNode] = {}
    edges: dict[str, OverviewEdge] = {}
    shared_risk: dict[str, int] = {}  # max seed-actor risk touching each shared node

    def upsert_node(
        nid: str,
        ntype: str,
        label: str | None = None,
        risk: int | None = None,
        is_focus: bool = False,
    ) -> None:
        node = nodes.get(nid)
        if node is None:
            nodes[nid] = OverviewNode(id=nid, type=ntype, label=label or nid, risk=risk, is_focus=is_focus)
            return
        if is_focus:
            node.is_focus = True
        if risk is not None and (node.risk is None or risk > node.risk):
            node.risk = risk

    def add_edge(edge: OverviewEdge) -> None:
        edges.setdefault(edge.id, edge)

    top_id = seeds[0].entity_id if seeds else None

    for alert in seeds:
        actor = alert.entity_id
        upsert_node(actor, "employee", risk=alert.risk_score, is_focus=(actor == top_id))

        for rc in alert.reason_codes:
            # Rule/pattern hub: actors that fire the same detection rule share a modus operandi.
            # This is the main link-density driver — it clusters otherwise-isolated actors.
            code = rc.code
            if code:
                pid = f"RULE-{code}"
                upsert_node(pid, "system", label=code.replace("_", " ").title())
                add_edge(
                    OverviewEdge(
                        id=f"{actor}=>{pid}", source=actor, target=pid, type="shares_pattern"
                    )
                )
                shared_risk[pid] = max(shared_risk.get(pid, 0), alert.risk_score)

            detail = rc.detail or ""
            if not detail:
                continue
            amt = _AMOUNT_RE.search(detail)
            amount = int(amt.group(1).replace(",", "")) if amt else None

            for ntype, etype, pattern in _TOKEN_RULES:
                for tok in pattern.findall(detail):
                    if tok == actor:
                        continue
                    upsert_node(tok, ntype)
                    add_edge(
                        OverviewEdge(
                            id=f"{actor}->{tok}",
                            source=actor,
                            target=tok,
                            type=etype,
                            collusion=(etype == "mule"),
                            amount_inr=amount if etype == "transaction" else None,
                        )
                    )
                    shared_risk[tok] = max(shared_risk.get(tok, 0), alert.risk_score)

            # Only wire a direct actor↔actor collusion edge for genuine maker-checker evidence.
            if "checker" in detail.lower() or "maker" in detail.lower():
                for tok in _EMP_RE.findall(detail):
                    if tok == actor:
                        continue
                    upsert_node(tok, "employee")
                    if f"{tok}~{actor}" not in edges:
                        add_edge(
                            OverviewEdge(
                                id=f"{actor}~{tok}",
                                source=actor,
                                target=tok,
                                type="maker_checker",
                                collusion=True,
                            )
                        )
                    shared_risk[tok] = max(shared_risk.get(tok, 0), alert.risk_score)

    # Tint shared (non-actor) nodes by the riskiest actor linked to them, so hot systems glow.
    for nid, risk in shared_risk.items():
        node = nodes.get(nid)
        if node is not None and node.type != "employee" and node.risk is None:
            node.risk = risk

    AUDIT.write(
        actor=principal.user_id,
        actor_role=principal.role,
        action="graph.overview",
        target="overview",
    )
    return GraphOverview(
        entity_id="overview",
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        min_score=min_score,
    )
