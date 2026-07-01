"""L6.5 — Privileged-Action Interdiction gate (action-gate service, :8096).

A synchronous Policy-Decision-Point the SOURCE systems (pam-shim today; CyberArk/CBS/IGA in prod)
call BEFORE a privileged staff action proceeds. It returns ALLOW | STEP_UP | HOLD_FOR_REVIEW and
records hash-chained-style audit. Hawk-Eye is **policy-author + audit-sink only** — it has no
actuator and never reaches into a source system; the source enforces the decision locally.

ALERT-ONLY & natural justice (SBI v Rajesh Agarwal): governs only REVERSIBLE staff actions, NEVER
money (`object.amount` is never read); STEP_UP re-auths and lets the actor proceed; HOLD routes to a
four-eyes human review (no self-review) whose approval only PERMITS human-initiated execution —
nothing auto-executes, nothing auto-classifies a person.

Endpoints:
  POST /api/v1/actions/evaluate           {actor, action, object, request_id}  -> ActionDecision
  POST /api/v1/step-ups/{id}/challenge    {method, approver}                   -> approved
  GET  /api/v1/step-ups/{id}                                                    -> status
  GET  /api/v1/holds/{id}                                                       -> hold detail
  POST /api/v1/holds/{id}/decision        {decider, approve, justification}    -> four-eyes outcome
  GET  /api/v1/holds ; GET /health ; GET /metrics
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel, Field

from agsvc.policy_engine import GATE, Decision

app = FastAPI(title="hawk-eye action-gate (L6.5)", version="1.0.0")

# In-memory stores (governance-DB persistence is SCAFFOLD).
DECISIONS: dict[str, dict] = {}   # request_id -> decision dict (idempotency)
STEP_UPS: dict[str, dict] = {}    # challenge_id -> step-up record
HOLDS: dict[str, dict] = {}       # hold_id -> hold record
AUDIT: list[dict] = []            # append-only decision/audit log

DECISION_CTR = Counter("action_gate_decisions_total", "L6.5 decisions", ["decision"])
CHALLENGE_CTR = Counter("action_gate_challenges_total", "step-up challenges", ["result"])
HOLD_CTR = Counter("action_gate_holds_total", "holds", ["result"])
DEGRADED_CTR = Counter("action_gate_degraded_total", "degraded evaluations")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _audit(action: str, target: str, detail: dict) -> str:
    audit_id = "aud_" + uuid.uuid4().hex[:12]
    AUDIT.append({"audit_id": audit_id, "ts": _now(), "action": action, "target": target,
                  "detail": detail})
    return audit_id


class ActionEvent(BaseModel):
    """A privileged STAFF action to evaluate. NOTE: no money field is gated — `object` may carry
    context but `object.amount` is deliberately never read (alert-only invariant)."""

    actor: dict = Field(..., description="{employee_id, role, privileged_flag}")
    action: dict = Field(..., description="{verb, channel}")
    object: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    features: dict = Field(default_factory=dict)
    request_id: str = Field(..., description="caller idempotency key")
    partner_id: str | None = None
    sod_score: float = 0.0
    opa_deny: bool = False
    governance_available: bool = True


class StepUpBody(BaseModel):
    method: str = Field("mfa", pattern="^(mfa|manager_approval)$")
    approver: str | None = None


class HoldDecisionBody(BaseModel):
    decider: str
    approve: bool
    justification: str = Field(..., min_length=3)


def _decision_payload(event: ActionEvent) -> dict:
    actor_id = str(event.actor.get("employee_id", ""))
    verb = str(event.action.get("verb", "")).lower()
    privileged = bool(event.actor.get("privileged_flag"))
    result = GATE.evaluate(
        verb, event.features, sod_score=event.sod_score, opa_deny=event.opa_deny,
        governance_available=event.governance_available, privileged=privileged,
    )
    action_id = "act_" + uuid.uuid4().hex[:12]
    payload = {
        "action_id": action_id,
        "request_id": event.request_id,
        "decision": result.decision.value,
        "severity": result.severity,
        "reason_codes": result.reason_codes,
        "challenge_id": None,
        "hold_id": None,
        "model_version": GATE.fingerprint,
        "evaluated_at": _now(),
        "degraded": result.degraded,
        "degraded_reason": result.degraded_reason,
        "actor_id": actor_id,
        "verb": verb,
    }
    if result.degraded:
        DEGRADED_CTR.inc()

    if result.decision == Decision.STEP_UP:
        cid = "chg_" + uuid.uuid4().hex[:10]
        STEP_UPS[cid] = {"challenge_id": cid, "request_id": event.request_id, "actor_id": actor_id,
                         "status": "pending", "method": None, "approver": None, "ts": _now()}
        payload["challenge_id"] = cid
    elif result.decision == Decision.HOLD_FOR_REVIEW:
        hid = "hold_" + uuid.uuid4().hex[:10]
        HOLDS[hid] = {
            "hold_id": hid, "request_id": event.request_id, "subject": actor_id, "verb": verb,
            "status": "pending_review", "reason_codes": result.reason_codes, "severity": result.severity,
            # natural-justice binding (verbatim hitl-gate semantics)
            "proportionality": "reversible staff action held pending second-approver review",
            "explanation": "; ".join(rc["detail"] for rc in result.reason_codes) or "policy hold",
            "dpia_binding": True, "decider": None, "justification": None, "ts": _now(),
        }
        payload["hold_id"] = hid

    payload["audit_id"] = _audit("action.evaluate", actor_id,
                                 {"request_id": event.request_id, "decision": result.decision.value,
                                  "verb": verb})
    DECISION_CTR.labels(decision=result.decision.value).inc()
    return payload


@app.post("/api/v1/actions/evaluate")
def evaluate(event: ActionEvent) -> dict:
    # Idempotency: a replayed request_id returns the same decision — UNLESS its step-up was since
    # approved, in which case the re-attempt is ALLOWed (the actor cleared the challenge).
    prior = DECISIONS.get(event.request_id)
    if prior is not None:
        cid = prior.get("challenge_id")
        if cid and STEP_UPS.get(cid, {}).get("status") == "approved":
            allow = {**prior, "decision": Decision.ALLOW.value, "challenge_id": None,
                     "reason_codes": [{"source": "gate", "code": "STEP_UP_CLEARED",
                                       "detail": "step-up challenge approved; action permitted"}],
                     "evaluated_at": _now()}
            DECISIONS[event.request_id] = allow
            DECISION_CTR.labels(decision=Decision.ALLOW.value).inc()
            return allow
        return prior
    payload = _decision_payload(event)
    DECISIONS[event.request_id] = payload
    return payload


@app.post("/api/v1/step-ups/{challenge_id}/challenge")
def challenge(challenge_id: str, body: StepUpBody) -> dict:
    su = STEP_UPS.get(challenge_id)
    if su is None:
        raise HTTPException(status_code=404, detail="unknown challenge")
    # A manager_approval must name a DIFFERENT approver than the acting staffer (four-eyes).
    if body.method == "manager_approval" and (not body.approver or body.approver == su["actor_id"]):
        raise HTTPException(status_code=403, detail="manager approval requires a distinct approver")
    su.update(status="approved", method=body.method, approver=body.approver, decided_ts=_now())
    _audit("action.step_up", su["actor_id"], {"challenge_id": challenge_id, "method": body.method})
    CHALLENGE_CTR.labels(result="approved").inc()
    return su


@app.get("/api/v1/step-ups/{challenge_id}")
def get_step_up(challenge_id: str) -> dict:
    su = STEP_UPS.get(challenge_id)
    if su is None:
        raise HTTPException(status_code=404, detail="unknown challenge")
    return su


@app.get("/api/v1/holds")
def list_holds() -> dict:
    return {"items": list(HOLDS.values()), "count": len(HOLDS)}


@app.get("/api/v1/holds/{hold_id}")
def get_hold(hold_id: str) -> dict:
    h = HOLDS.get(hold_id)
    if h is None:
        raise HTTPException(status_code=404, detail="unknown hold")
    return h


@app.post("/api/v1/holds/{hold_id}/decision")
def decide_hold(hold_id: str, body: HoldDecisionBody) -> dict:
    h = HOLDS.get(hold_id)
    if h is None:
        raise HTTPException(status_code=404, detail="unknown hold")
    # Four-eyes / SoD: the reviewer may not be the subject of the held action (no self-review).
    if body.decider == h["subject"]:
        raise HTTPException(status_code=403, detail="four-eyes: the subject cannot resolve their own hold")
    if h["status"] != "pending_review":
        raise HTTPException(status_code=409, detail="hold already resolved")
    # Approval only PERMITS human-initiated execution — the gate never auto-executes anything.
    h["status"] = "approved_via_four_eyes" if body.approve else "rejected"
    h["outcome"] = "permitted_for_human_initiated_execution" if body.approve else "denied_by_reviewer"
    h.update(decider=body.decider, justification=body.justification, decided_ts=_now())
    _audit("action.hold_decision", h["subject"],
           {"hold_id": hold_id, "approve": body.approve, "decider": body.decider})
    HOLD_CTR.labels(result=h["status"]).inc()
    return h


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "action-gate", "policy_version": GATE.fingerprint,
            "alert_only": True, "gates_money": False}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
