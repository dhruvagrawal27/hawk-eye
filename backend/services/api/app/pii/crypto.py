"""Field-level PII encryption + masking (BACKEND-18, blueprint Part 19.3).

AES-256-GCM authenticated encryption for PII/PAN at rest (the re-id vault stores ciphertext, never
plaintext). The data-encryption key is derived from a PLATFORM-custodied secret (Vault/KMS/HSM in
production; a labelled local-dev placeholder here). mTLS in transit is terminated by the PLATFORM
service mesh; this module covers the at-rest + field-level masking half.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_AAD = b"hawk-eye-pii-v1"


def _key() -> bytes:
    """Derive a 256-bit DEK from the PLATFORM-custodied field key (KMS/HSM in prod)."""
    return hashlib.sha256(settings.pii_field_key.encode("utf-8")).digest()


def encrypt_field(plaintext: str) -> str:
    """Encrypt one PII field → base64(nonce || ciphertext). Authenticated (GCM)."""
    aes = AESGCM(_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), _AAD)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt_field(blob: str) -> str:
    """Decrypt a base64(nonce || ciphertext) field produced by :func:`encrypt_field`."""
    raw = base64.urlsafe_b64decode(blob.encode("ascii"))
    nonce, ct = raw[:12], raw[12:]
    aes = AESGCM(_key())
    return aes.decrypt(nonce, ct, _AAD).decode("utf-8")


def mask(value: str, *, keep: int = 2) -> str:
    """Display-mask a PII value (e.g. account number) keeping the last ``keep`` chars."""
    if not value:
        return value
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


def at_rest_status() -> dict:
    """Posture summary surfaced on /health and admin views."""
    return {
        "field_level_encryption": "AES-256-GCM",
        "key_custody": "platform_vault_kms_hsm" if not settings.is_local else "local_dev_placeholder",
        "mtls_in_transit": settings.mtls_internal,
    }
