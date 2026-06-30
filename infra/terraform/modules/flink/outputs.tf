# --- flink module outputs ----------------------------------------------------
output "application_arn" {
  description = "Managed Flink application ARN."
  value       = aws_kinesisanalyticsv2_application.main.arn
}

output "application_name" {
  description = "Managed Flink application name."
  value       = aws_kinesisanalyticsv2_application.main.name
}
