# --- alb module inputs -------------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "vpc_id" {
  description = "VPC id (for the target group)."
  type        = string
  default     = null
}

variable "public_subnet_ids" {
  description = "PUBLIC subnet ids — the ALB is the only thing here."
  type        = list(string)
  default     = []
}

variable "security_group_id" {
  description = "ALB security group id (443 in from internet)."
  type        = string
  default     = null
}

variable "certificate_arn" {
  description = <<-EOT
    ACM certificate ARN for the HTTPS listener. A dummy default keeps `plan`
    credential-free; supply a real ARN at apply time.
  EOT
  type        = string
  default     = "arn:aws:acm:ap-south-1:000000000000:certificate/00000000-0000-0000-0000-000000000000"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
