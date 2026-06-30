# --- mwaa module outputs -----------------------------------------------------
output "environment_arn" {
  description = "MWAA environment ARN."
  value       = aws_mwaa_environment.main.arn
}

output "webserver_url" {
  description = "MWAA (private) webserver URL."
  value       = aws_mwaa_environment.main.webserver_url
}
