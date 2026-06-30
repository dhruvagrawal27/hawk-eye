# --- env: aws — passthrough variables ----------------------------------------
variable "project" {
  description = "Project slug."
  type        = string
  default     = "hawk-eye"
}

variable "env" {
  description = "Environment name."
  type        = string
  default     = "pilot"
}

variable "region" {
  description = "AWS region (ap-south-1 for residency, Part 16)."
  type        = string
  default     = "ap-south-1"
}

variable "residency" {
  description = "Data-residency label."
  type        = string
  default     = "in-india"
}
