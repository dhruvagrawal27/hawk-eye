# =============================================================================
# Hawk-Eye — on-prem mirror module: Kafka [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Kafka equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: MSK -> self-managed Kafka)
# Task     : PLATFORM-7 (onprem-kafka)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "kafka" {
  triggers = {
    component = "Apache Kafka 3.8.1 (KRaft)"
    image     = "apache/kafka:3.8.1"
    swaps     = "MSK -> self-managed Kafka"
    prefix    = var.name_prefix
  }
}
