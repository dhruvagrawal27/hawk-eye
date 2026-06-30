"""Model signing — detached Ed25519 signature over the artifact bundle (DATABASE-8).

Blueprint Part 23.3 (model signing, signature verified on load, l.864-865) +
Part 19.2 (encrypted+signed artifacts) + Part 19.4 (signature verification on load).

The signature covers the **whole bundle** (every file except ``signature.sig``)
via a deterministic manifest digest:

    manifest = { rel_path: sha256(file_bytes) for each file }   # sorted
    digest   = sha256( canonical_json(manifest) )
    signature = Ed25519_sign(private_key, digest)               # detached

So tampering with ANY artifact file (onnx, native booster, a transform-chain step,
the calibrator, or metadata.json) invalidates the signature → load is rejected.

On-prem: a **local** Ed25519 key (no cloud KMS). 1:1 swap = cosign/sigstore or a
KMS/HSM-held key (PLATFORM key custody seam). Keys are read from env paths and are
**git-ignored** (`registry/keys/`), never committed.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Mapping, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DEFAULT_KEY_DIR = os.getenv("REGISTRY_KEY_DIR", "registry/keys")
PRIVATE_KEY_FILE = "registry_signing_ed25519.pem"
PUBLIC_KEY_FILE = "registry_signing_ed25519.pub"


class SignatureError(RuntimeError):
    """Raised when a signature fails to verify (tamper or wrong key)."""


# ---------------------------------------------------------------------------
# bundle digest
# ---------------------------------------------------------------------------
def bundle_manifest(files: Mapping[str, bytes]) -> Dict[str, str]:
    """``{rel_path: sha256hex(file_bytes)}`` for every file in the bundle."""
    return {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}


def bundle_digest(files: Mapping[str, bytes]) -> bytes:
    """Deterministic SHA-256 over the sorted manifest (the thing we sign)."""
    manifest = bundle_manifest(files)
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).digest()


# ---------------------------------------------------------------------------
# key management (local, on-prem)
# ---------------------------------------------------------------------------
def generate_keypair(
    key_dir: str | os.PathLike[str] = DEFAULT_KEY_DIR,
) -> Tuple[Path, Path]:
    """Generate a local Ed25519 keypair for dev signing. Returns (priv, pub) paths."""
    d = Path(key_dir)
    d.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    priv_path = d / PRIVATE_KEY_FILE
    pub_path = d / PUBLIC_KEY_FILE
    priv_path.write_bytes(
        priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    os.chmod(priv_path, 0o600)
    return priv_path, pub_path


def _key_dir() -> str:
    """Resolved at CALL time (honours REGISTRY_KEY_DIR set after import)."""
    return os.getenv("REGISTRY_KEY_DIR", DEFAULT_KEY_DIR)


def load_private_key(path: str | None = None) -> Ed25519PrivateKey:
    p = Path(
        path or os.getenv("REGISTRY_SIGNING_KEY") or f"{_key_dir()}/{PRIVATE_KEY_FILE}"
    )
    if not p.exists():
        # dev convenience: auto-generate INTO the requested key's directory so the
        # path we read == the path we just wrote (filenames match the env paths).
        generate_keypair(p.parent)
    key = serialization.load_pem_private_key(p.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):  # pragma: no cover
        raise SignatureError("registry signing key is not Ed25519")
    return key


def load_public_key(path: str | None = None) -> Ed25519PublicKey:
    p = Path(
        path or os.getenv("REGISTRY_PUBLIC_KEY") or f"{_key_dir()}/{PUBLIC_KEY_FILE}"
    )
    if not p.exists():
        generate_keypair(p.parent)
    key = serialization.load_pem_public_key(p.read_bytes())
    if not isinstance(key, Ed25519PublicKey):  # pragma: no cover
        raise SignatureError("registry public key is not Ed25519")
    return key


# ---------------------------------------------------------------------------
# sign / verify
# ---------------------------------------------------------------------------
def sign_bundle(
    files: Mapping[str, bytes], private_key: Ed25519PrivateKey | None = None
) -> bytes:
    """Detached signature (raw 64 bytes) over the bundle digest."""
    key = private_key or load_private_key()
    return key.sign(bundle_digest(files))


def verify_bundle(
    files: Mapping[str, bytes],
    signature: bytes,
    public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Return True iff ``signature`` validates the bundle. Never raises on bad sig."""
    key = public_key or load_public_key()
    try:
        key.verify(signature, bundle_digest(files))
        return True
    except InvalidSignature:
        return False


def require_valid(
    files: Mapping[str, bytes],
    signature: bytes,
    public_key: Ed25519PublicKey | None = None,
) -> None:
    """Raise :class:`SignatureError` unless the signature validates the bundle."""
    if not verify_bundle(files, signature, public_key):
        raise SignatureError(
            "model artifact signature INVALID — refusing to load (tamper or wrong key)"
        )
