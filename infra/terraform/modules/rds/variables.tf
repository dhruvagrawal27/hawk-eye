# --- rds module inputs -------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "subnet_ids" {
  description = "Private DATA subnet ids for the DB subnet group."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "Data-tier security group id."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for storage encryption."
  type        = string
  default     = null
}

variable "instance_class" {
  description = "RDS instance class (cost-conscious pilot, Part 26.3)."
  type        = string
  default     = "db.m6i.large"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
