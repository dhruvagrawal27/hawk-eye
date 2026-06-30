# =============================================================================
# Hawk-Eye — on-prem mirror module: Airflow [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted Airflow equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: MWAA -> Airflow)
# Task     : PLATFORM-7 (onprem-airflow)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "airflow" {
  triggers = {
    component = "Apache Airflow 2.10.4"
    image     = "apache/airflow:2.10.4"
    swaps     = "MWAA -> Airflow"
    prefix    = var.name_prefix
  }
}
