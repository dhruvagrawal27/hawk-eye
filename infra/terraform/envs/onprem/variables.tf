# --- env: onprem — passthrough variables -------------------------------------
variable "project" {
  description = "Project slug."
  type        = string
  default     = "hawk-eye"
}

variable "env" {
  description = "Environment name."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "Region label (kept ap-south-1 for residency parity, Part 16)."
  type        = string
  default     = "ap-south-1"
}

variable "residency" {
  description = "Data-residency label."
  type        = string
  default     = "in-india"
}
