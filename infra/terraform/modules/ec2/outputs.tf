# --- ec2 module outputs ------------------------------------------------------
output "clickhouse_private_ip" {
  description = "ClickHouse node private IP."
  value       = aws_instance.clickhouse.private_ip
}

output "serving_private_ip" {
  description = "Model-serving node private IP."
  value       = aws_instance.serving.private_ip
}

output "keycloak_private_ip" {
  description = "Keycloak node private IP."
  value       = aws_instance.keycloak.private_ip
}

output "instance_ids" {
  description = "All EC2 instance ids."
  value = {
    clickhouse = aws_instance.clickhouse.id
    serving    = aws_instance.serving.id
    keycloak   = aws_instance.keycloak.id
  }
}
