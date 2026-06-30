# =============================================================================
# Hawk-Eye — on-prem mirror module: Redis [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Redis equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: ElastiCache -> Redis)
# Task     : PLATFORM-7 (onprem-redis)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "redis" {
  triggers = {
    component = "Redis 7.4.1"
    image     = "redis:7.4.1-alpine"
    swaps     = "ElastiCache -> Redis"
    prefix    = var.name_prefix
  }
}
