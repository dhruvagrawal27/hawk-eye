# --- iam module outputs ------------------------------------------------------
output "ec2_role_arn" {
  description = "EC2 instance role ARN."
  value       = aws_iam_role.ec2.arn
}

output "ec2_instance_profile_name" {
  description = "EC2 instance profile name (attached to ClickHouse/serving/keycloak hosts)."
  value       = aws_iam_instance_profile.ec2.name
}

output "flink_role_arn" {
  description = "Managed Flink service role ARN."
  value       = aws_iam_role.flink.arn
}

output "mwaa_role_arn" {
  description = "MWAA execution role ARN."
  value       = aws_iam_role.mwaa.arn
}
