"""Audit memo for every generated narrative (ML-12; Part 25.4, BACKEND.md §7).

Every narrative — LLM or template — writes a memo so the provenance of every
AI-written word is auditable: ``provider, tee_attested, attestation_id, model,
prompt_hash, ts``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_AUDIT_PATH = os.path.join(
    REPO_ROOT, "ml", "_artifacts", "narratives", "audit_memos.jsonl"
)


@dataclass
class AuditMemo:
    provider: str
    tee_attested: bool
    attestation_id: Optional[str]
    model: Optional[str]
    prompt_hash: str
    ts: float
    alert_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def prompt_hash(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
    return h.hexdigest()


class AuditMemoWriter:
    """Append-only audit-memo log. # STUB: DATABASE owns the durable audit-archive bucket."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or DEFAULT_AUDIT_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def write(self, memo: AuditMemo) -> AuditMemo:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(memo.to_dict()) + "\n")
        return memo

    def all(self) -> list[dict]:
        if not os.path.isfile(self.path):
            return []
        with open(self.path) as fh:
            return [json.loads(line) for line in fh if line.strip()]


def make_memo(
    *,
    provider: str,
    tee_attested: bool,
    attestation_id: Optional[str],
    model: Optional[str],
    system_prompt: str,
    user_prompt: str,
    alert_id: Optional[str] = None,
    ts: Optional[float] = None,
) -> AuditMemo:
    return AuditMemo(
        provider=provider,
        tee_attested=tee_attested,
        attestation_id=attestation_id,
        model=model,
        prompt_hash=prompt_hash(system_prompt, user_prompt),
        ts=ts if ts is not None else time.time(),
        alert_id=alert_id,
    )
