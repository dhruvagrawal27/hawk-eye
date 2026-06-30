# --- onprem-redis module outputs ----------------------------------
output "component" {
  description = "Self-hosted Redis component identity (on-prem target)."
  value = {
    component = "Redis 7.4.1"
    image     = "redis:7.4.1-alpine"
    swaps     = "ElastiCache -> Redis"
  }
}
