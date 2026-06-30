#!/usr/bin/env bash
# Load the 3 platform secrets into Vault dev (PLATFORM-12, blueprint Part 25.3 / 26.1).
# NEVER hardcodes real values: reads from the environment (.env / CI secret store).
# In prod this is AWS Secrets Manager / SSM (Terraform modules/secrets); the values
# come from a sealed store, never git. The PII_HMAC_KEY is exposed to BACKEND's
# tokenizer by *reference* only (vault path), never inlined.
set -euo pipefail

export VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
export VAULT_TOKEN="${VAULT_DEV_ROOT_TOKEN_ID:-hawkeye-dev-root}"

echo "[vault] waiting for ${VAULT_ADDR} ..."
for i in $(seq 1 30); do
  if vault status >/dev/null 2>&1; then break; fi
  sleep 1
done

vault secrets enable -path=hawk-eye kv-v2 2>/dev/null || true

vault kv put hawk-eye/llm \
  NEAR_AI_API_KEY="${NEAR_AI_API_KEY:-dev-placeholder-near-ai-key}" \
  GROQ_API_KEY="${GROQ_API_KEY:-dev-placeholder-groq-key}"

vault kv put hawk-eye/pii \
  PII_HMAC_KEY="${PII_HMAC_KEY:-dev-only-hmac-key-rotate-in-vault}"

# Field-level PII encryption key (BACKEND field-encryption, Part 25.3) — by reference only.
vault kv put hawk-eye/field \
  FIELD_ENCRYPTION_KEY="${FIELD_ENCRYPTION_KEY:-dev-only-field-key-rotate-in-vault}"

# Model-registry signing key (cosign/registry signing, Part 23) — by reference only.
vault kv put hawk-eye/registry \
  REGISTRY_SIGNING_KEY="${REGISTRY_SIGNING_KEY:-dev-only-registry-signing-key-rotate-in-vault}"

# Least-privilege policy: BACKEND tokenizer can READ only the pii + field paths (Part 19.3 SoD).
vault policy write backend-tokenizer - <<'POLICY' 2>/dev/null || true
path "hawk-eye/data/pii"   { capabilities = ["read"] }
path "hawk-eye/data/field" { capabilities = ["read"] }
POLICY

echo "[vault] secrets loaded under hawk-eye/ (llm, pii, field, registry). Read by reference only:"
echo "        vault kv get hawk-eye/pii   # BACKEND tokenizer uses this path, never a literal key"
