# `registry/keys/` — model-signing keys (DATABASE-8)

> **Dev-only, generated, never committed** (golden rule 2). The Ed25519 keypair
> here signs model artifacts (`signing.py`). Generate with:
>
> ```python
> from registry.mlflow.signing import generate_keypair
> generate_keypair()   # writes registry_signing_ed25519.pem (+ .pub)
> ```
>
> (`load_private_key()`/`load_public_key()` auto-generate on first use for dev.)

## Prod / AWS swap (key custody seam)
The local PEM is the **on-prem dev** stand-in. In production the signing key is
held in **Vault/HSM** (PLATFORM owns custody, Part 9.3); swap to **cosign/sigstore**
or a KMS-held key — only `signing.load_private_key/load_public_key` change. The
artifact format (`signature.sig` detached over the bundle digest) is unchanged.

Env overrides: `REGISTRY_SIGNING_KEY` (private PEM path), `REGISTRY_PUBLIC_KEY`
(public PEM path), `REGISTRY_KEY_DIR` (default dir).
