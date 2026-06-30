# --- s3 module outputs -------------------------------------------------------
output "artifacts_bucket_id" {
  description = "Models/datasets bucket name."
  value       = aws_s3_bucket.artifacts.id
}

output "artifacts_bucket_arn" {
  description = "Models/datasets bucket ARN."
  value       = aws_s3_bucket.artifacts.arn
}

output "audit_bucket_id" {
  description = "CloudTrail WORM audit bucket name."
  value       = aws_s3_bucket.audit.id
}

output "audit_bucket_arn" {
  description = "CloudTrail WORM audit bucket ARN."
  value       = aws_s3_bucket.audit.arn
}
