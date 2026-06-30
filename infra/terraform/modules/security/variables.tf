# --- security module inputs --------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "alb_arn" {
  description = "ALB ARN to associate the WAF web ACL with."
  type        = string
  default     = null
}

variable "trail_bucket_id" {
  description = "S3 WORM audit bucket name for CloudTrail."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for CloudTrail log encryption."
  type        = string
  default     = null
}

variable "account_id" {
  description = <<-EOT
    AWS account id for Inspector v2 enablement. A placeholder 12-digit default
    keeps validate/plan credential-free; set the real account id at apply time.
  EOT
  type        = string
  default     = "000000000000"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
