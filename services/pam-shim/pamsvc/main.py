"""PAM integration shim (PLATFORM-15, blueprint Part 9.3 / Part 19.3, MOCK).

MOCK of a Privileged Access Management broker (real swap: CyberArk / BeyondTrust).
Records simulated privileged-admin sessions (who/when/what + a session-recording stub),
enforces **least-privilege** per persona, and rejects **shared/anonymous accounts** — the
exact anti-pattern this whole platform is built to catch (Part 19.3). "The watchers must
themselves be watched": every platform-admin action here is auditable.

Ties to the SoD `administrator` persona (PLATFORM-33). Endpoints:
  POST /sessions/start            {admin, role, reason}     -> session_id (+ recording stub)
  POST /sessions/{id}/command     {command}                  -> allowed/denied (least-privilege)
  POST /sessions/{id}/end                                    -> session summary + recording_uri
  GET  /sessions                                             -> audit view (who/when/what)
  GET  /health, /metrics
"""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel

app = FastAPI(title="hawk-eye pam-shim (MOCK)", version="1.0.0")
SESSIONS: dict[str, dict] = {}

CMDS = Counter("pam_commands_total", "privileged commands", ["result"])

# Least-privilege command allow-lists per platform role (no standing super-admin).
ROLE_ALLOW = {
    "platform_admin": {"restart_service", "view_logs", "rotate_secret", "scale", "deploy_config"},
    "sre_oncall": {"restart_service", "view_logs", "scale", "failover"},
    "db_admin": {"backup", "restore", "view_schema"},
    "security_admin": {"rotate_secret", "view_audit", "update_policy"},
}
# Accounts that must NEVER be used (shared/anonymous) — Part 19.3.
FORBIDDEN_ACCOUNTS = {"root", "admin", "shared", "service", "svc", "ops", ""}


class StartReq(BaseModel):
    admin: str            # named human admin (no shared accounts)
    role: str
    reason: str           # justification (four-eyes/ticket ref in prod)


class CmdReq(BaseModel):
    command: str
    target: str = ""


def _audit(entry: dict) -> None:
    # Prod: append to hawkeye.audit (WORM). Here: held in the session record.
    entry["audit_ts"] = time.time()


@app.get("/health")
def health():
    return {"status": "ok", "service": "pam-shim", "mock": True}


@app.post("/sessions/start")
def start(req: StartReq):
    if req.admin.lower() in FORBIDDEN_ACCOUNTS:
        raise HTTPException(403, f"shared/anonymous account '{req.admin}' forbidden (Part 19.3)")
    if req.role not in ROLE_ALLOW:
        raise HTTPException(400, f"unknown role '{req.role}'")
    if not req.reason.strip():
        raise HTTPException(400, "a justification is required for privileged access")
    sid = "pam_" + uuid.uuid4().hex[:10]
    SESSIONS[sid] = {
        "session_id": sid, "admin": req.admin, "role": req.role, "reason": req.reason,
        "started_ts": time.time(), "ended_ts": None,
        "recording": {"status": "recording", "stub": True},  # session-recording stub
        "commands": [],
    }
    _audit({"event": "session.start", "session_id": sid, "admin": req.admin})
    return {"session_id": sid, "recording": "started (stub)", "allowed_commands": sorted(ROLE_ALLOW[req.role])}


@app.post("/sessions/{sid}/command")
def command(sid: str, req: CmdReq):
    s = SESSIONS.get(sid)
    if not s or s["ended_ts"] is not None:
        raise HTTPException(404, "no active session")
    allowed = req.command in ROLE_ALLOW[s["role"]]
    record = {"command": req.command, "target": req.target, "ts": time.time(),
              "allowed": allowed}
    s["commands"].append(record)
    _audit({"event": "session.command", "session_id": sid, **record})
    CMDS.labels("allowed" if allowed else "denied").inc()
    if not allowed:
        raise HTTPException(403, f"least-privilege: '{req.command}' not permitted for role '{s['role']}'")
    return {"executed": True, "command": req.command, "recorded": True}


@app.post("/sessions/{sid}/end")
def end(sid: str):
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "no such session")
    s["ended_ts"] = time.time()
    s["recording"] = {"status": "stored", "recording_uri": f"worm://pam-recordings/{sid}.cast", "stub": True}
    _audit({"event": "session.end", "session_id": sid})
    return {"session_id": sid, "duration_s": round(s["ended_ts"] - s["started_ts"], 2),
            "command_count": len(s["commands"]),
            "denied_count": sum(1 for c in s["commands"] if not c["allowed"]),
            "recording_uri": s["recording"]["recording_uri"]}


@app.get("/sessions")
def list_sessions():
    return {"sessions": list(SESSIONS.values())}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
