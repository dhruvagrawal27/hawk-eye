# --- flink module inputs -----------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "subnet_ids" {
  description = "Private COMPUTE subnet ids for the VPC-attached app."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "Compute-tier security group id."
  type        = string
  default     = null
}

variable "service_role_arn" {
  description = "Managed Flink service execution role ARN (from iam module)."
  type        = string
  default     = null
}

variable "artifact_bucket_id" {
  description = "S3 artifacts bucket holding the Flink application JAR/ZIP."
  type        = string
  default     = null
}

variable "application_jar_key" {
  description = "S3 object key of the Flink application package."
  type        = string
  default     = "flink/hawk-eye-streaming.zip"
}

variable "flink_runtime" {
  description = "Managed Flink runtime environment (BOM pin family 1.20.x)."
  type        = string
  default     = "FLINK-1_20"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
