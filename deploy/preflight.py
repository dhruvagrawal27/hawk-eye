#!/usr/bin/env python3
"""Deploy-gating end-to-end preflight.

Exercises the whole vertical against a RUNNING stack and exits non-zero on any failure, so a deploy
can gate on it (bootstrap.sh runs it after `compose up`). Checks: login → ingest a fraud event →
the online pipeline emits an alert → a narrative is generated → disposition writes a label → the
realtime stream is live. No external deps (urllib only).

    python3 deploy/preflight.py [BASE_URL]      # default http://localhost:8000
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
_failures = 0


def _req(method: str, url: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}
    except Exception as e:  # noqa: BLE001
        print(f"  connection error: {e}")
        return 0, {}


def check(name: str, ok: bool, detail: str = "") -> bool:
    global _failures
    print(f"  [{PASS if ok else FAIL}] {name}{(' — ' + detail) if detail else ''}")
    if not ok:
        _failures += 1
    return ok


EVENT = {
    "event_id": "evt_preflight",
    "ts": "2026-07-01T02:14:07Z",
    "actor": {
        "employee_id": "EMP-pf1", "role": "ops_checker", "dept": "trade_finance",
        "branch": "BR-219", "privileged_flag": True, "tenure_days": 2840,
    },
    "action": {"verb": "approve_payment", "channel": "cbs", "maker_checker": "checker"},
    "object": {"beneficiary_id": "BEN-pf", "account_id": "ACCT-7", "amount": 4800000, "currency": "INR"},
    "context": {
        "is_off_hours": True, "src_ip": "10.20.4.31", "device": "WS-114", "geo": "Mumbai",
        "session_id": "sess_pf", "layer": "application",
    },
    "linkage": {"maker_id": "EMP-m9", "checker_id": "EMP-pf1"},
}


def main() -> int:
    print(f"Hawk-Eye preflight → {BASE}\n")

    # /health is at root on the backend; behind nginx it's exposed as /healthz — try both.
    s, h = _req("GET", f"{BASE}/health")
    if s != 200:
        s, h = _req("GET", f"{BASE}/healthz")
    check("API health", s == 200 and h.get("status") == "ok", f"status={s}")

    s, body = _req("POST", f"{API}/auth/login", {"username": "EMP-tl01", "password": "hawk-eye"})
    token = body.get("access_token")
    check("login (team-lead)", s == 200 and bool(token))
    if not token:
        print("\n  cannot continue without a token")
        return 1

    s, body = _req("POST", f"{API}/events/ingest?full=true", EVENT, token)
    alert = body.get("alert") or {}
    aid = alert.get("alert_id")
    check("ingest → alert emitted", s == 200 and bool(aid), f"alert={aid} risk={alert.get('risk_score')}")

    if aid:
        s, a = _req("GET", f"{API}/alerts/{aid}", token=token)
        check("alert readback", s == 200 and a.get("alert_id") == aid,
              f"risk={a.get('risk_score')} layers={a.get('contributing_layers')}")

        s, nar = _req("POST", f"{API}/narratives/{aid}", {}, token)
        check("narrative generated", s == 200 and bool(nar.get("narrative")),
              f"provider={nar.get('provider')}")

        s, d = _req("POST", f"{API}/alerts/{aid}/disposition",
                    {"outcome": "fraud", "notes": "preflight"}, token)
        check("disposition → label written", s == 200 and bool(d.get("label_written") or d.get("status")),
              f"status={d.get('status')}")

    s, st = _req("GET", f"{API}/stream/status")
    check("realtime stream live", s == 200 and st.get("mode") in ("inprocess", "kafka"),
          f"mode={st.get('mode')}")

    print()
    if _failures:
        print(f"\033[31mPREFLIGHT FAILED — {_failures} check(s) failed\033[0m")
        return 1
    print("\033[32mPREFLIGHT PASSED — A→Z vertical is live\033[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
