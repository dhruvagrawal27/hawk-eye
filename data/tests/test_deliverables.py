"""Deliverable-existence + contract-parity checks (gap guard for DATA-1 / DATA-17 / BACKEND.md §1)."""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _p(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def test_proto_exists_with_all_field_groups():
    proto = open(_p("data", "schemas", "l0_event.proto"), encoding="utf-8").read()
    for msg in ("message Actor", "message Action", "message ObjectRef",
                "message Context", "message Linkage", "message L0Event"):
        assert msg in proto, f"proto missing {msg}"
    for f in ("employee_id", "verb", "amount", "is_off_hours", "swift_ref", "event_id"):
        assert f in proto, f"proto missing field {f}"


def test_onboarding_playbook_exists_with_8_stages():
    doc = open(_p("data", "docs", "source_onboarding_playbook.md"), encoding="utf-8").read().lower()
    for stage in ("discovery", "schema mapping", "connector build", "dq rules",
                  "backfill", "lineage", "shadow", "promote"):
        assert stage in doc, f"playbook missing stage {stage}"


def test_onboarding_status_tracker_advances():
    from data.ingest.onboarding_status import OnboardingRegistry, STAGES
    reg = OnboardingRegistry.with_defaults()
    dash = reg.dashboard()
    assert len(dash) >= 8 and all("stage" in d and "status" in d for d in dash)
    s = reg.sources["cbs"]
    start = s.stage
    s.advance(True)
    assert s.stage != start and s.stage in STAGES


def test_sample_event_matches_backend_contract_fields():
    """sample_event.json must carry the five L0 field groups (BACKEND.md §1 parity)."""
    sample = json.load(open(_p("data", "schemas", "sample_event.json"), encoding="utf-8"))
    for group in ("actor", "action", "object", "context", "linkage"):
        assert group in sample, f"sample missing field group {group}"
    assert sample["actor"]["employee_id"].startswith("EMP-")
    assert sample["event_id"].startswith("evt_")
    assert sample["ts"].endswith("Z")
    # validate via the schema module
    from data.schemas.l0_event import validate_event
    assert validate_event(sample) == []


def test_requirements_file_present():
    assert os.path.exists(_p("data", "requirements.txt"))
