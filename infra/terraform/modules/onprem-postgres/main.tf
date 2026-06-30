# =============================================================================
# Hawk-Eye — on-prem mirror module: PostgreSQL [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted PostgreSQL equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: RDS -> PostgreSQL)
# Task     : PLATFORM-7 (onprem-postgres)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "postgres" {
  triggers = {
    component = "PostgreSQL 17.2"
    image     = "postgres:17.2"
    swaps     = "RDS -> PostgreSQL"
    prefix    = var.name_prefix
  }
}
