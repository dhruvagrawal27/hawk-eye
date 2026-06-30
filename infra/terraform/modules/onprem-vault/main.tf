# =============================================================================
# Hawk-Eye — on-prem mirror module: Vault [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Vault equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: Secrets Manager -> HashiCorp Vault)
# Task     : PLATFORM-7 (onprem-vault)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "vault" {
  triggers = {
    component = "HashiCorp Vault 1.18"
    image     = "hashicorp/vault:1.18"
    swaps     = "Secrets Manager -> HashiCorp Vault"
    prefix    = var.name_prefix
    # KV v2 paths that hold the 3 runtime secrets (values injected out-of-band).
    kv_paths = join(",", [for n in var.secret_names : "secret/${var.name_prefix}/${n}"])
  }
}
