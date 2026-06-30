# =============================================================================
# Hawk-Eye — KMS module (at-rest encryption keys)  [SCAFFOLD]
# Purpose : Customer-managed KMS key used by S3 (SSE-KMS), RDS, MSK, EBS, secrets.
# Blueprint: Part 26.1 (Keys → AWS KMS), Part 26.2 (KMS at rest), Part 26.4 (KMS→HSM)
# Task     : PLATFORM-12 (kms)
# =============================================================================

# SCAFFOLD: a single customer-managed key with rotation. Real deploy may split
# per-service keys; one key keeps the plan-only scaffold readable.
resource "aws_kms_key" "main" {
  description             = "${var.name_prefix} at-rest encryption key (S3/RDS/MSK/EBS/secrets)"
  deletion_window_in_days = 30
  enable_key_rotation     = true # annual rotation (Part 19 crypto hygiene)
  tags                    = var.tags
}

# Friendly alias for the key.
resource "aws_kms_alias" "main" {
  name          = "alias/${var.name_prefix}-main"
  target_key_id = aws_kms_key.main.key_id
}
