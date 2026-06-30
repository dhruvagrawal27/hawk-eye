# --- onprem-keycloak module outputs ----------------------------------
output "component" {
  description = "Self-hosted Keycloak component identity (on-prem target)."
  value = {
    component = "Keycloak 25.0.6"
    image     = "quay.io/keycloak/keycloak:25.0.6"
    swaps     = "Keycloak on EC2 -> Keycloak on-prem"
  }
}
