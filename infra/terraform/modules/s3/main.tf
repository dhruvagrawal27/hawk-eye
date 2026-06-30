# =============================================================================
# Hawk-Eye — S3 module (SSE-KMS + versioned + object-lock) [SCAFFOLD]
# Purpose : Object store for models/datasets (artifacts) + a WORM audit bucket for
#           CloudTrail. SSE-KMS encryption, versioning, object-lock, public-access
#           fully blocked.
# Blueprint: Part 26.1 (Object store → S3 SSE-KMS/versioned/object-lock), Part 26.4 (→ MinIO)
# Task     : PLATFORM-7 (s3)
# =============================================================================

# --- Artifacts bucket (models / synthetic datasets) --------------------------
resource "aws_s3_bucket" "artifacts" {
  bucket        = "${var.name_prefix}-artifacts"
  force_destroy = false
  # object-lock must be enabled at create time for WORM retention support.
  object_lock_enabled = true
  tags                = merge(var.tags, { purpose = "models-datasets" })
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_object_lock_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    default_retention {
      mode = "GOVERNANCE" # GOVERNANCE allows privileged override; COMPLIANCE = immutable
      days = 365
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Audit bucket (CloudTrail target; WORM via COMPLIANCE lock) ---------------
resource "aws_s3_bucket" "audit" {
  bucket              = "${var.name_prefix}-audit"
  force_destroy       = false
  object_lock_enabled = true
  tags                = merge(var.tags, { purpose = "cloudtrail-audit-worm" })
}

resource "aws_s3_bucket_versioning" "audit" {
  bucket = aws_s3_bucket.audit.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode = "COMPLIANCE" # immutable WORM — audit trail cannot be tampered (Part 19)
      days = 2555         # ~7 years record retention (RBI record-keeping)
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
