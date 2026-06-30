# =============================================================================
# Hawk-Eye — on-prem mirror module: MinIO [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted MinIO equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: S3 -> MinIO)
# Task     : PLATFORM-7 (onprem-minio)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "minio" {
  triggers = {
    component = "MinIO (S3 API, object-lock/WORM)"
    image     = "minio/minio:RELEASE.2024-12-18T13-15-44Z"
    swaps     = "S3 -> MinIO"
    prefix    = var.name_prefix
  }
}
