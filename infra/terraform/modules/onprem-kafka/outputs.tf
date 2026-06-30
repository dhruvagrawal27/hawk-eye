# --- onprem-kafka module outputs ----------------------------------
output "component" {
  description = "Self-hosted Kafka component identity (on-prem target)."
  value = {
    component = "Apache Kafka 3.8.1 (KRaft)"
    image     = "apache/kafka:3.8.1"
    swaps     = "MSK -> self-managed Kafka"
  }
}
