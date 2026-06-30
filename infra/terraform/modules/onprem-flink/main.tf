# =============================================================================
# Hawk-Eye — on-prem mirror module: Flink [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Flink equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: Managed Flink -> Flink cluster)
# Task     : PLATFORM-7 (onprem-flink)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "flink" {
  triggers = {
    component = "Apache Flink 1.20.0 cluster"
    image     = "flink:1.20.0-scala_2.12-java17"
    swaps     = "Managed Flink -> Flink cluster"
    prefix    = var.name_prefix
  }
}
