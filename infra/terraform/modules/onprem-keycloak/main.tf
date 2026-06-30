# =============================================================================
# Hawk-Eye — on-prem mirror module: Keycloak [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Keycloak equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: Keycloak on EC2 -> Keycloak on-prem)
# Task     : PLATFORM-7 (onprem-keycloak)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "keycloak" {
  triggers = {
    component = "Keycloak 25.0.6"
    image     = "quay.io/keycloak/keycloak:25.0.6"
    swaps     = "Keycloak on EC2 -> Keycloak on-prem"
    prefix    = var.name_prefix
  }
}
