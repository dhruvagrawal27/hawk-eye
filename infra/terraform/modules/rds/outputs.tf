# --- rds module outputs ------------------------------------------------------
output "endpoint" {
  description = "RDS PostgreSQL connection endpoint."
  value       = aws_db_instance.main.endpoint
}

output "db_name" {
  description = "Initial database name."
  value       = aws_db_instance.main.db_name
}

output "master_secret_arn" {
  description = "ARN of the RDS-managed master user secret (in Secrets Manager)."
  # master_user_secret is a list of objects; take the first when present.
  value = try(aws_db_instance.main.master_user_secret[0].secret_arn, null)
}
