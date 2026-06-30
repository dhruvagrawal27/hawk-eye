# --- msk module inputs -------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "subnet_ids" {
  description = "Private DATA subnet ids (one broker per subnet/AZ)."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "Data-tier security group id."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for at-rest encryption."
  type        = string
  default     = null
}

variable "kafka_version" {
  description = "MSK-supported Kafka version (BOM pin family 3.8.x)."
  type        = string
  default     = "3.8.1"
}

variable "broker_instance_type" {
  description = "MSK broker instance type (cost-conscious pilot, Part 26.3)."
  type        = string
  default     = "kafka.m7g.large"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
