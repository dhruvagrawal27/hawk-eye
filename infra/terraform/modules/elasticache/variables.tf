# --- elasticache module inputs -----------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "subnet_ids" {
  description = "Private DATA subnet ids."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "Data-tier security group id."
  type        = string
  default     = null
}

variable "node_type" {
  description = "ElastiCache node type (cost-conscious pilot, Part 26.3)."
  type        = string
  default     = "cache.m6g.large"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
