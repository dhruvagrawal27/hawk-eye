# --- onprem-vault module outputs ----------------------------------
output "component" {
  description = "Self-hosted Vault component identity (on-prem target)."
  value = {
    component = "HashiCorp Vault 1.18"
    image     = "hashicorp/vault:1.18"
    swaps     = "Secrets Manager -> HashiCorp Vault"
  }
}
