# --- lightsail-instances module inputs ---------------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "availability_zone" {
  description = "Lightsail AZ (must be in ap-south-1 for residency)."
  type        = string
  default     = "ap-south-1a"
}

variable "blueprint_id" {
  description = "Lightsail OS blueprint."
  type        = string
  default     = "ubuntu_22_04"
}

variable "bundle_id" {
  description = "Lightsail bundle (fixed-price size)."
  type        = string
  default     = "large_2_0"
}

variable "tags" {
  description = "Tags to apply."
  type        = map(string)
  default     = {}
}
