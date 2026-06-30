# --- KMS module outputs ------------------------------------------------------
output "key_arn" {
  description = "ARN of the customer-managed KMS key."
  value       = aws_kms_key.main.arn
}

output "key_id" {
  description = "Key id of the customer-managed KMS key."
  value       = aws_kms_key.main.key_id
}

output "alias_name" {
  description = "KMS alias name."
  value       = aws_kms_alias.main.name
}
