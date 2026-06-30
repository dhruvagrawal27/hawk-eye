#!/usr/bin/env python3
"""Mock HSM key-custody wrapper via PKCS#11 (PLATFORM-13, Part 9.3/19.3, MOCK).

DEV-ONLY. Performs sign/encrypt operations against a SoftHSM2 token so platform
services can use a real PKCS#11 surface for dev key custody. Production swaps a real
HSM (CloudHSM / Thales Luna): the PKCS#11 interface stays the same, only the module
path + credentials change — so callers don't change.

Usage:
    python key_custody.py sign   --data "payload"          # RSA sign via token
    python key_custody.py encrypt --data "pii-field"        # AES encrypt via token

Falls back to a clearly-labelled in-process soft-crypto path if python-pkcs11 / SoftHSM
is unavailable (so dev/CI keeps working); the audit note records which path was used.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os

MODULE = os.environ.get("PKCS11_MODULE", "/usr/lib/softhsm/libsofthsm2.so")
TOKEN_LABEL = os.environ.get("TOKEN_LABEL", "hawk-eye-dev")
USER_PIN = os.environ.get("USER_PIN", "1234")
KEY_LABEL = os.environ.get("KEY_LABEL", "pii-field-key")


def _pkcs11_available() -> bool:
    try:
        import pkcs11  # noqa: F401
        return os.path.exists(MODULE)
    except Exception:
        return False


def hsm_sign(data: bytes) -> dict:
    if _pkcs11_available():
        import pkcs11
        lib = pkcs11.lib(MODULE)
        token = lib.get_token(token_label=TOKEN_LABEL)
        with token.open(user_pin=USER_PIN) as session:
            priv = session.get_key(label="hawk-eye-signing", object_class=pkcs11.ObjectClass.PRIVATE_KEY)
            sig = priv.sign(data, mechanism=pkcs11.Mechanism.SHA256_RSA_PKCS)
        return {"backend": "softhsm2-pkcs11", "signature": base64.b64encode(sig).decode(), "mock": True}
    # soft fallback (clearly labelled)
    sig = hmac.new(b"dev-soft-hsm-fallback", data, hashlib.sha256).hexdigest()
    return {"backend": "soft-fallback", "signature": sig, "mock": True,
            "note": "SoftHSM/python-pkcs11 unavailable; using in-process fallback (DEV)"}


def hsm_encrypt(data: bytes) -> dict:
    if _pkcs11_available():
        import pkcs11
        from pkcs11 import Mechanism
        lib = pkcs11.lib(MODULE)
        token = lib.get_token(token_label=TOKEN_LABEL)
        with token.open(user_pin=USER_PIN) as session:
            key = session.get_key(label=KEY_LABEL, object_class=pkcs11.ObjectClass.SECRET_KEY)
            iv = session.generate_random(128)
            ct = key.encrypt(data, mechanism=Mechanism.AES_CBC_PAD, mechanism_param=iv)
        return {"backend": "softhsm2-pkcs11", "iv": base64.b64encode(iv).decode(),
                "ciphertext": base64.b64encode(ct).decode(), "mock": True}
    from cryptography.fernet import Fernet
    key = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"dev-field-key").digest()))
    return {"backend": "soft-fallback", "ciphertext": key.encrypt(data).decode(), "mock": True,
            "note": "SoftHSM unavailable; using in-process Fernet (DEV)"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock HSM key custody (PLATFORM-13, DEV ONLY)")
    ap.add_argument("op", choices=["sign", "encrypt"])
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    out = hsm_sign(a.data.encode()) if a.op == "sign" else hsm_encrypt(a.data.encode())
    import json
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
