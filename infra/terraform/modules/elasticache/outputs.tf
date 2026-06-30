# --- elasticache module outputs ----------------------------------------------
output "primary_endpoint" {
  description = "Redis primary endpoint address."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint" {
  description = "Redis reader endpoint address."
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "replication_group_id" {
  description = "Replication group id."
  value       = aws_elasticache_replication_group.main.replication_group_id
}
