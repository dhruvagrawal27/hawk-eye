# =============================================================================
# Hawk-Eye — on-prem mirror module: HSM [SCAFFOLD / placeholder]
# Purpose : Documents the self-hosted HSM equivalent for the on-prem target.
#           On-prem is NOT cloud-provisioned by Terraform — it is brought up by
#           Ansible/Helm/compose. This module is a null_resource marker so the
#           on-prem target plans cleanly and records the component + swap source.
# Blueprint: Part 26.4 (AWS -> on-prem migration: KMS -> HSM)
# Task     : PLATFORM-7 (onprem-hsm)
# =============================================================================

# Placeholder marker — emits the component identity at plan/apply with no cloud
# call. Real provisioning lives in deploy/ (compose/helm) + ops/ (ansible).
resource "null_resource" "hsm" {
  triggers = {
    component = "PKCS#11 HSM (SoftHSM2 in dev)"
    image     = "softhsm2:2.6.1"
    swaps     = "KMS -> HSM"
    prefix    = var.name_prefix
  }
}
