# --- onprem-hsm module outputs ----------------------------------
output "component" {
  description = "Self-hosted HSM component identity (on-prem target)."
  value = {
    component = "PKCS#11 HSM (SoftHSM2 in dev)"
    image     = "softhsm2:2.6.1"
    swaps     = "KMS -> HSM"
  }
}
