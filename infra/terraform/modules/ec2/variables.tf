# --- ec2 module inputs -------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "ami_id" {
  description = <<-EOT
    AMI id for the hosts. A dummy default keeps `plan` credential-free (no AMI
    data-source lookup). Replace with a real ap-south-1 AMI at apply time.
  EOT
  type        = string
  default     = "ami-00000000000000000" # SCAFFOLD placeholder; replace at apply
}

variable "subnet_id" {
  description = "Private COMPUTE subnet id to place the hosts in."
  type        = string
  default     = null
}

variable "security_group_id" {
  description = "Compute-tier security group id."
  type        = string
  default     = null
}

variable "iam_instance_profile" {
  description = "EC2 instance profile name (from iam module)."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "KMS CMK ARN for EBS encryption."
  type        = string
  default     = null
}

variable "clickhouse_instance_type" {
  description = "ClickHouse node type (Part 26.3 sizing)."
  type        = string
  default     = "r6i.xlarge"
}

variable "app_instance_type" {
  description = "Serving / Keycloak node type (Part 26.3 sizing)."
  type        = string
  default     = "m6i.large"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
