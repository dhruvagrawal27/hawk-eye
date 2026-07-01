"""Entity-360 contracts: profile, timeline, graph, peers (BACKEND-19, blueprint Part 11/24.2).

All identifiers are tokenized (``EMP-*``/``ACCT-*``/``BEN-*``); unmask is a separate audited route.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Severity


class EntityProfile(BaseModel):
    entity_id: str = Field(..., examples=["EMP-7f3a"])
    role: str | None = None
    dept: str | None = None
    branch: str | None = None
    peer_group: str | None = None
    tenure_days: int | None = None
    privileged_flag: bool = False
    leaver_flag: bool = False
    risk_score: int = Field(0, ge=0, le=100)
    severity: Severity = Severity.LOW
    open_alerts: int = 0
    pii_tokenized: bool = True


class TimelineEvent(BaseModel):
    """One row on the unified transaction+access+data+change timeline."""

    ts: str
    lane: str = Field(..., description="transaction | access | data | change | hr")
    verb: str
    channel: str | None = None
    detail: str = ""
    event_id: str | None = None
    amount_inr: int | None = None
    is_off_hours: bool = False  # outside IST bank hours (Mon–Fri 08:00–20:00)


class EntityTimeline(BaseModel):
    entity_id: str
    events: list[TimelineEvent] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    kind: str = Field(..., description="employee | beneficiary | account | device | ip")
    label: str | None = None
    risk: int | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str = Field(..., description="maker_checker | pays | shares_device | shares_ip | owns")
    weight: float = 1.0


class EntityGraph(BaseModel):
    entity_id: str
    ring_id: str | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class PeerComparison(BaseModel):
    entity_id: str
    peer_group: str | None = None
    dimension: str = Field(..., description="The flagged dimension being compared")
    actor_value: float
    peer_mean: float
    peer_p95: float
    z_score: float
    is_outlier: bool


class UnmaskRequest(BaseModel):
    tokens: list[str] = Field(
        default_factory=list, description="Tokens to re-identify; empty = all on the entity"
    )
    justification: str = Field(
        "", description="Case-scoped reason (required for Relationship Manager, logged)"
    )


class UnmaskResponse(BaseModel):
    entity_id: str
    mapping: dict[str, str] = Field(
        default_factory=dict, description="token → real value (audited; never logged)"
    )
    audit_id: str
