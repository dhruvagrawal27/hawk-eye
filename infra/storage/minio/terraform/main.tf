# =============================================================================
# Hawk-Eye — storage-tier object store: Terraform module STUB (plan-only) — DATABASE-1
# Blueprint: Part 23.3 (object-lock + SSE-KMS, l.864-865); Part 21.5 (l.823-824).
# -----------------------------------------------------------------------------
# SEAM: PLATFORM owns the runtime `infra/` + the cloud S3 module
# (infra/terraform/modules/s3) and the on-prem MinIO marker
# (infra/terraform/modules/onprem-minio). THIS module is the DATABASE-owned
# *storage-tier* contract: it declares the EXACT buckets + lock/versioning/SSE
# intent so PLATFORM can wire it into the global stack and apply the AWS
# equivalent. It is `plan`-only (null_resource marker; no cloud calls), mirroring
# the local compose (bootstrap_minio.sh) 1:1.
#
# AWS swap (documented, applied by PLATFORM): each bucket below becomes an
# `aws_s3_bucket` with `object_lock_enabled=true` (models, audit-archive),
# `aws_s3_bucket_versioning=Enabled`, and
# `aws_s3_bucket_server_side_encryption_configuration` = aws:kms (SSE-KMS).
# =============================================================================
terraform {
  required_version = ">= 1.9"
}

variable "name_prefix" {
  description = "Project-env prefix (e.g. hawkeye-prod)."
  type        = string
  default     = "hawkeye-local"
}

locals {
  buckets = {
    models = {
      object_lock = true
      versioning  = true
      sse         = "SSE-KMS" # MinIO SSE-S3 locally; aws:kms in cloud
      retention   = "30d-COMPLIANCE"
      purpose     = "signed model artifacts (DATABASE-7/8)"
    }
    datasets = {
      object_lock = false
      versioning  = true
      sse         = "SSE-KMS"
      retention   = "lifecycle"
      purpose     = "partitioned-Parquet datasets + DVC remote (Part 21.5)"
    }
    "feature-snapshots" = {
      object_lock = false
      versioning  = true
      sse         = "SSE-KMS"
      retention   = "lifecycle"
      purpose     = "offline feature snapshots"
    }
    "audit-archive" = {
      object_lock = true
      versioning  = true
      sse         = "SSE-KMS"
      retention   = "3650d-COMPLIANCE"
      purpose     = "WORM sealed audit records (DATABASE-6)"
    }
  }
}

# Plan-only marker: emits the storage-tier contract without any cloud call.
resource "null_resource" "object_store_contract" {
  for_each = local.buckets
  triggers = {
    bucket      = each.key
    object_lock = tostring(each.value.object_lock)
    versioning  = tostring(each.value.versioning)
    sse         = each.value.sse
    retention   = each.value.retention
    purpose     = each.value.purpose
    prefix      = var.name_prefix
  }
}

output "buckets" {
  description = "The storage-tier bucket contract (consumed by PLATFORM's S3 module)."
  value       = local.buckets
}
