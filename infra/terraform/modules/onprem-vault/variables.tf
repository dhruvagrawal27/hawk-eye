# --- onprem-vault module inputs -----------------------------------
variable "name_prefix" {
  description = "Name prefix (project-env)."
  type        = string
}

variable "secret_names" {
  description = "Runtime secret names held in Vault KV (values injected out-of-band)."
  type        = list(string)
  default     = ["NEAR_AI_API_KEY", "GROQ_API_KEY", "PII_HMAC_KEY"]
}
