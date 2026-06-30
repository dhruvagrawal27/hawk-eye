# --- onprem-flink module outputs ----------------------------------
output "component" {
  description = "Self-hosted Flink component identity (on-prem target)."
  value = {
    component = "Apache Flink 1.20.0 cluster"
    image     = "flink:1.20.0-scala_2.12-java17"
    swaps     = "Managed Flink -> Flink cluster"
  }
}
