# Secrets management (PLATFORM-12)

Blueprint **Part 26.1** (Secrets/KMS) + **Part 19.3** (data protection) + **Part 25.3** (PII key).

Holds the **3 platform secrets**: `NEAR_AI_API_KEY`, `GROQ_API_KEY`, `PII_HMAC_KEY`.

- **Local/dev:** HashiCorp **Vault** in `-dev` mode (compose service `vault`, :8200).
  `make up` starts it; `vault-init` loads the secrets from the environment via
  `bootstrap-secrets.sh` (never from git).
- **AWS:** **Secrets Manager + SSM Parameter Store** (Terraform `modules/secrets`),
  with **KMS** encryption-at-rest (`modules/kms`, SSE-KMS).
- **Migration:** `Secrets Manager → Vault`, `KMS → HSM` (migration-map.md).

## The golden constraints
1. **Never hardcoded, never in git.** `.env.example` carries only labelled placeholders.
2. **`PII_HMAC_KEY` exposed by reference.** BACKEND's tokenizer (BACKEND-17, Part 25.3)
   reads `hawk-eye/pii` from Vault — it never receives a literal key. SoD policy
   `backend-tokenizer` grants read-only to that one path.
3. **Field-level PII key** lives in the HSM (SoftHSM dev, PLATFORM-13); `PII_HMAC_KEY`
   (tokenization) lives in Vault. Two different keys, two different custodians.

## Use
```bash
make up                      # starts vault + vault-init
export VAULT_ADDR=http://localhost:8200 VAULT_TOKEN=hawkeye-dev-root
vault kv get hawk-eye/pii    # BACKEND reads this path, not a literal
```
