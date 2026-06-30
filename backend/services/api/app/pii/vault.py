"""Local re-identification vault (BACKEND-17, blueprint Part 25.3).

The token↔real mapping lives ONLY here and is **never sent out**. Real values are stored
encrypted at rest (``crypto.encrypt_field``). Re-identification (``resolve``) is exercised by the
audited ``POST /entities/{id}/unmask`` route for authorized users; the vault itself does not check
authorization (the route does) but it never logs plaintext.

# STUB: DATABASE (Postgres, encrypted vault table). In-memory shim honouring the contract so the
unmask path runs locally; swap the dict for the Postgres table with no route change.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pii import crypto


@dataclass
class VaultEntry:
    token: str
    field_type: str
    ciphertext: str  # encrypt_field(real_value) — never plaintext


class ReidVault:
    def __init__(self) -> None:
        self._entries: dict[str, VaultEntry] = {}

    def store(self, token: str, real_value: str, field_type: str = "employee") -> None:
        """Record a token→real mapping (idempotent; real value encrypted at rest)."""
        if token in self._entries:
            return
        self._entries[token] = VaultEntry(
            token=token, field_type=field_type, ciphertext=crypto.encrypt_field(real_value)
        )

    def resolve(self, token: str) -> str | None:
        """Re-identify a single token → real value (authorized callers only)."""
        entry = self._entries.get(token)
        return crypto.decrypt_field(entry.ciphertext) if entry else None

    def resolve_many(self, tokens: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for tok in tokens:
            real = self.resolve(tok)
            if real is not None:
                out[tok] = real
        return out

    def known_tokens(self) -> list[str]:
        return list(self._entries.keys())

    def __len__(self) -> int:
        return len(self._entries)


# Process-wide vault (one re-id store for the control plane).
VAULT = ReidVault()
