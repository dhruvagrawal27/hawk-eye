# --- onprem-postgres module outputs ----------------------------------
output "component" {
  description = "Self-hosted PostgreSQL component identity (on-prem target)."
  value = {
    component = "PostgreSQL 17.2"
    image     = "postgres:17.2"
    swaps     = "RDS -> PostgreSQL"
  }
}
