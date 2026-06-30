# Mock HSM — SoftHSM2 key custody (PLATFORM-13)

Blueprint **Part 9.3** (HSM for keys) + **Part 19.3** (data protection). **MOCK / DEV-ONLY.**

> **SoftHSM2 is a software PKCS#11 token for development. It is NOT a real HSM.**
> Production swaps a **physical/cloud HSM** (AWS CloudHSM or Thales Luna). The PKCS#11
> interface is identical, so `key_custody.py` callers do not change — only the module
> path + credentials do. On AWS the at-rest path uses **KMS** (PLATFORM-12); the HSM
> covers key custody / field-level PII keys (BACKEND-18 seam).

## Files
- `init-token.sh` — `make softhsm-init`: initialises the `hawk-eye-dev` token and
  generates an AES field-encryption key + an RSA signing key inside it.
- `softhsm2.conf` — dev token-store config (token dir is gitignored).
- `key_custody.py` — sign/encrypt via PKCS#11; falls back to a labelled in-process path
  if SoftHSM is absent (so CI keeps working).

## Use
```bash
apt-get install -y softhsm2 opensc      # or: brew install softhsm
make softhsm-init
python deploy/hsm/softhsm/key_custody.py sign --data "audit-record-123"
python deploy/hsm/softhsm/key_custody.py encrypt --data "EMP-7f3a"
```

## Where the keys are used
- **PII field encryption** (BACKEND-18): the AES `pii-field-key` wraps field-level PII
  before storage. BACKEND's tokenizer holds `PII_HMAC_KEY` separately in Vault (PLATFORM-12).
- **Artifact/audit signing**: the RSA `hawk-eye-signing` key signs audit records / dev
  artifacts (prod: cosign + real HSM, PLATFORM-17).
