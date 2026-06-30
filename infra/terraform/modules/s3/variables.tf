# --- s3 module inputs --------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env). Buckets are <prefix>-artifacts / <prefix>-audit."
  type        = string
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for SSE-KMS."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
