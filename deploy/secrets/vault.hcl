# HashiCorp Vault config (PLATFORM-12). Reference for a non-dev (prod-like) deployment.
# Local compose runs Vault in -dev mode (in-memory, auto-unsealed). On AWS the equivalent
# is Secrets Manager + SSM (Terraform infra/terraform/modules/secrets); KMS provides
# encryption-at-rest (modules/kms). Migration: Secrets Manager -> Vault (migration-map.md).
ui = true
storage "file" {
  path = "/vault/data"
}
listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/vault/tls/vault.crt"   # mTLS in prod; dev uses tls_disable
  tls_key_file  = "/vault/tls/vault.key"
}
# Seal with the HSM/KMS in prod (auto-unseal):
# seal "pkcs11"  { lib = "/usr/lib/softhsm/libsofthsm2.so" ... }   # dev/HSM
# seal "awskms"  { region = "ap-south-1" kms_key_id = "<kms-key>" }  # AWS
api_addr     = "https://vault.internal:8200"
disable_mlock = false
