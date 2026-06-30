"""Narrative route + audit memo contract (BACKEND-20, blueprint Part 25.4)."""

from __future__ import annotations


def test_narrative_returns_labelled_ai_output_and_memo(client, auth):
    r = client.post("/api/v1/narratives/alr_demo01", headers=auth("analyst"))
    assert r.status_code == 200
    body = r.json()
    assert body["ai_generated"] is True  # UI must label it AI-generated (Part 25.7)
    assert body["provider"] in ("near_ai", "groq", "template")
    assert isinstance(body["tee_attested"], bool)
    assert body["narrative"]

    from app.store.alert_store import ALERTS
    memos = ALERTS.narrative_memos("alr_demo01")
    assert memos, "an audit memo must be persisted"
    memo = memos[-1]
    assert memo.provider in ("near_ai", "groq", "template")
    assert memo.prompt_hash.startswith("sha256:")
    assert memo.ts.endswith("Z")

    from app.audit.writer import AUDIT
    assert any(e.action == "narrative.generate" for e in AUDIT.all())


def test_narrative_route_never_breaks_when_llm_down(client, auth):
    # Local mode: the ML gateway is unreachable, so the deterministic template fallback is used and
    # the route still returns 200 (UI never goes dark).
    r = client.post("/api/v1/narratives/alr_demo03", headers=auth("senior"))
    assert r.status_code == 200
    assert r.json()["provider"] == "template"
    assert r.json()["tee_attested"] is False
