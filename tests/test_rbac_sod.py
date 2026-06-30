"""SoD RBAC tests (PLATFORM-33, Part 19.3/19.6) — builder≠labeler≠actor≠administrator."""
import pytest
import route_guards as rg


def test_each_persona_only_its_own_duty():
    cases = {
        "builder": "build_model", "labeler": "label_data",
        "actor": "act_on_alert", "administrator": "administer_platform",
    }
    for persona, own_duty in cases.items():
        assert rg.can([persona], own_duty) is True
        for other_duty in cases.values():
            if other_duty != own_duty and rg.DUTY_PERSONA[other_duty] != persona:
                assert rg.can([persona], other_duty) is False


def test_enforce_blocks_cross_duty():
    tok = rg.make_token("u_builder", ["builder"])
    rg.enforce(tok, "build_model")  # ok
    with pytest.raises(rg.SoDViolation):
        rg.enforce(tok, "act_on_alert")  # builder cannot act


def test_toxic_combination_rejected():
    with pytest.raises(rg.SoDViolation):
        rg.assert_no_toxic_combo(["builder", "labeler"])
    with pytest.raises(rg.SoDViolation):
        rg.assert_no_toxic_combo(["actor", "administrator"])


def test_clean_single_persona_ok():
    rg.assert_no_toxic_combo(["actor"])  # no exception


def test_token_roundtrip():
    tok = rg.make_token("u_actor", ["actor"])
    assert rg.personas_of(tok) == ["actor"]
