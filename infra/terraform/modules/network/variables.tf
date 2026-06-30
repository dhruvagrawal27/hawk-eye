# --- network module inputs ---------------------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block."
  type        = string
  default     = "10.42.0.0/16"
}

variable "azs" {
  description = "AZs to spread subnets across (multi-AZ HA)."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

variable "egress_allowlist_fqdns" {
  description = "The only FQDNs permitted outbound (enforced at proxy/DNS-firewall)."
  type        = list(string)
  default     = ["cloud-api.near.ai", "api.groq.com"]
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
