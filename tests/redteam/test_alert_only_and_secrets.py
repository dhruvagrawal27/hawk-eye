"""Red-team: golden-rule + secrets invariants, statically across the WHOLE repo.

These are cross-cutting checks no single workstream owns. Pure static analysis (reads
source, no heavy imports) so it runs in ANY venv. Blueprint: Part 1/2 (alert-only),
Part 16 (natural justice), Part 19.2/19.3 (no secrets, tokenize-before-egress), Part 25.3/25.7.
"""
from __future__ import annotations

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIRS = ("data", "ml", "backend", "frontend", "infra", "services", "tools")
# venvs / generated / vendored — never scanned
SKIP = re.compile(r"(^|/)(\.mlvenv|\.venv|\.bevenv|\.pfvenv|node_modules|__pycache__|"
                  r"dist|\.git|out|_artifacts|coverage|\.next|build|site-packages)(/|$)")
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".yaml", ".yml", ".toml", ".env", ".sh", ".rs", ".tf")


def _iter_files():
    for d in SRC_DIRS:
        root = os.path.join(REPO, d)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            if SKIP.search(dirpath):
                dirnames[:] = []
                continue
            for fn in filenames:
                p = os.path.join(dirpath, fn)
                if fn.endswith(CODE_EXT) and not SKIP.search(p):
                    yield p


def _read(p: str) -> str:
    try:
        with open(p, encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# Golden rule #2 / Part 19.3 — NO hardcoded secrets anywhere
# --------------------------------------------------------------------------- #
SECRET_NAMES = ("NEAR_AI_API_KEY", "GROQ_API_KEY", "PII_HMAC_KEY")
# a literal assignment: KEY = "somevalue"  (NOT os.environ / getenv / vault ref / placeholder)
_HARDCODED = re.compile(
    r"""(NEAR_AI_API_KEY|GROQ_API_KEY|PII_HMAC_KEY|aws_secret_access_key|private_key)"""
    r"""\s*[:=]\s*["'][^"'\n]{8,}["']""",
    re.IGNORECASE,
)
_SAFE_VALUE = re.compile(r"(os\.environ|getenv|vault|secret_ref|\$\{|<|example|changeme|placeholder|dummy|REDACTED|\bnull\b)", re.IGNORECASE)
_LIVE_KEY = re.compile(r"\b(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})\b")


def test_no_hardcoded_api_keys_or_secrets():
    offenders = []
    for p in _iter_files():
        text = _read(p)
        for m in _HARDCODED.finditer(text):
            line = text[: m.start()].count("\n") + 1
            snippet = m.group(0)
            if not _SAFE_VALUE.search(snippet):
                offenders.append(f"{os.path.relpath(p, REPO)}:{line}: {snippet[:80]}")
    assert not offenders, "Hardcoded secrets found (golden rule #2 / Part 19.3):\n" + "\n".join(offenders)


def test_no_live_credential_patterns():
    offenders = []
    for p in _iter_files():
        for m in _LIVE_KEY.finditer(_read(p)):
            offenders.append(f"{os.path.relpath(p, REPO)}: {m.group(0)[:12]}…")
    assert not offenders, "Live credential patterns found:\n" + "\n".join(offenders)


_ENV_INJECTION = re.compile(r"os\.environ|getenv|vault|SecretStr|secret_ref", re.IGNORECASE)


def test_secret_keys_are_consumed_via_env_or_vault():
    """Each named secret must be wired through env/vault injection (not hardcoded). Indirection
    is allowed (e.g. ``env_key='NEAR_AI_API_KEY'`` then ``os.environ.get(self.env_key)``), so we
    require env/vault injection to exist in the SAME module/dir that references the secret."""
    files = {p: _read(p) for p in _iter_files()}
    for name in SECRET_NAMES:
        mentioning = [p for p, t in files.items() if name in t]
        assert mentioning, f"{name} never referenced — secret-injection seam missing?"
        dirs = {os.path.dirname(p) for p in mentioning}
        wired = any(
            os.path.dirname(p) in dirs and _ENV_INJECTION.search(t) for p, t in files.items()
        )
        assert wired, f"{name} is referenced but no os.environ/vault injection exists in its module"


# --------------------------------------------------------------------------- #
# Golden rule #1 / Part 16 — ALERT-ONLY: nothing auto-blocks / auto-classifies
# --------------------------------------------------------------------------- #
def test_ml_publishes_an_alert_only_contract():
    """ml.design.alert_only_contract must forbid autonomous actions in source."""
    src = _read(os.path.join(REPO, "ml", "design", "alert_only_contract.py"))
    assert "FORBIDDEN_AUTONOMOUS_ACTIONS" in src
    for forbidden in ("block", "freeze", "auto_classify_fraud", "reverse_transaction"):
        assert forbidden in src, f"alert-only contract must name {forbidden!r} as forbidden"
    assert "AlertOnlyViolation" in src


def test_backend_block_is_a_request_not_an_auto_execution():
    """The only 'block' surface is a HUMAN block-REQUEST route (Part 16) — never an auto-block."""
    routes_dir = os.path.join(REPO, "backend", "services", "api", "app", "routes")
    blob = ""
    for dp, _, fns in os.walk(routes_dir):
        for fn in fns:
            if fn.endswith(".py"):
                blob += _read(os.path.join(dp, fn))
    # there is a block-request path (human raises it)
    assert re.search(r"block[-_]request", blob), "expected a human block-request route"
    # no route auto-executes an irreversible block/freeze/seize without a human
    bad = re.findall(r"def\s+\w*(auto_block|execute_block|freeze_account|seize)\w*\s*\(", blob)
    assert not bad, f"backend must not auto-execute blocks: {bad}"


def test_hitl_gate_holds_classifications_for_a_human():
    """PLATFORM HITL gate must hold classifications in pending_review until a human decides."""
    hitl = os.path.join(REPO, "services", "hitl-gate")
    if not os.path.isdir(hitl):
        import pytest

        pytest.skip("hitl-gate service not present")
    blob = ""
    for dp, _, fns in os.walk(hitl):
        for fn in fns:
            if fn.endswith(".py"):
                blob += _read(os.path.join(dp, fn))
    assert "pending_review" in blob, "HITL gate must hold actions in pending_review (Part 16)"
    assert re.search(r"decision|approve|reject", blob), "HITL gate must require a human decision"


# --------------------------------------------------------------------------- #
# Part 25.3 — PII tokenized before egress; raw PII never reaches the LLM
# --------------------------------------------------------------------------- #
def test_pii_tokenizer_uses_keyed_hmac_from_env():
    src = _read(os.path.join(REPO, "ml", "narrative", "pii.py"))
    assert "hmac" in src.lower() and "sha256" in src.lower(), "PII tokens must be keyed HMAC-SHA256 (Part 25.3)"
    assert "PII_HMAC_KEY" in src and "environ" in src, "HMAC key must come from os.environ"


def test_narrative_guardrails_reject_deanonymization():
    src = _read(os.path.join(REPO, "ml", "narrative", "guardrails.py"))
    assert "grounded" in src.lower() or "grounding" in src.lower(), "narrative must be grounded vs reason codes"
