# --- lightsail-network module inputs -----------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "instance_name" {
  description = "Name of the Lightsail instance to attach the static IP / ports to."
  type        = string
  default     = null
}

variable "ssh_admin_cidrs" {
  description = "Admin CIDRs allowed to SSH (NOT 0.0.0.0/0). Tighten at apply time."
  type        = list(string)
  default     = ["10.0.0.0/8"] # placeholder admin range; replace with real bastion CIDR
}
