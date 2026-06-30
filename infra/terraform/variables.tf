# =============================================================================
# Hawk-Eye — Root input variables (parameterized target)
# Purpose : Single set of inputs driving the aws | onprem | lightsail deployment.
# Blueprint: Part 26.1 (AWS mapping), Part 16 (data residency in-India), Part 26.4
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# All defaults are SAFE / SYNTHETIC so the tree plans with zero real values.
# =============================================================================

# --- The deployment-target switch (the heart of the parameterization) --------
variable "target" {
  description = <<-EOT
    Which deployment target to instantiate.
      aws       = production-shaped pilot, EC2-in-VPC + managed services (Part 26.1) — RETAINED scale-up path.
      onprem    = production target, self-hosted open-source mirror (Part 26.4) — RETAINED.
      lightsail = the CHOSEN demo/pilot target (ADR-0001), compose stack on Lightsail.
  EOT
  type        = string
  default     = "lightsail"

  validation {
    # Restrict to exactly the three supported targets. Anything else fails plan early.
    condition     = contains(["aws", "onprem", "lightsail"], var.target)
    error_message = "var.target must be one of: aws | onprem | lightsail."
  }
}

# --- Identity / residency / tagging ------------------------------------------
variable "project" {
  description = "Project slug, used as a name prefix and tag."
  type        = string
  default     = "hawk-eye"
}

variable "env" {
  description = "Environment name (e.g. pilot, demo, prod)."
  type        = string
  default     = "pilot"
}

variable "region" {
  description = "AWS region. ap-south-1 (Mumbai) is mandatory for data residency (Part 16)."
  type        = string
  default     = "ap-south-1"

  validation {
    # Data-residency guard: keep the pilot in India. Override only with sign-off.
    condition     = can(regex("^ap-south-", var.region))
    error_message = "region must be an India region (ap-south-*) for data residency (Part 16)."
  }
}

variable "residency" {
  description = "Data-residency label applied to every workload (Part 16)."
  type        = string
  default     = "in-india"

  validation {
    condition     = var.residency == "in-india"
    error_message = "residency must be 'in-india' (Part 16 data residency)."
  }
}

# --- Egress allow-list (Part 26.2 / Part 19.3) -------------------------------
# Only the tokenized, TEE-protected LLM traffic may leave; everything else has
# NO internet egress. FQDN egress is enforced by a proxy / prefix-list at apply
# time (documented in modules/network) — listed here as the canonical allow-list.
variable "egress_allowlist_fqdns" {
  description = "The ONLY FQDNs permitted outbound (NEAR AI + Groq). Everything else = no egress."
  type        = list(string)
  default     = ["cloud-api.near.ai", "api.groq.com"]
}

# --- Network sizing (aws / lightsail VPC scaffold) ---------------------------
variable "vpc_cidr" {
  description = "VPC CIDR for the aws target (private-first)."
  type        = string
  default     = "10.42.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across (multi-AZ HA, Part 30)."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]
}

# --- The three runtime secret NAMES (never the values — golden rule) ---------
# Secrets Manager/SSM (AWS) or Vault (on-prem) hold the VALUES; IaC only knows NAMES.
variable "secret_names" {
  description = "Names of the runtime secrets (values injected out-of-band; never in TF)."
  type        = list(string)
  default     = ["NEAR_AI_API_KEY", "GROQ_API_KEY", "PII_HMAC_KEY"]
}

# --- Instance sizing (cost-conscious pilot, Part 26.3) -----------------------
variable "ec2_clickhouse_instance_type" {
  description = "ClickHouse analytics node (gp3 EBS). r6i.xlarge per Part 26.3 sizing."
  type        = string
  default     = "r6i.xlarge"
}

variable "ec2_app_instance_type" {
  description = "App/serving/keycloak general-purpose node. m6i.large per Part 26.3."
  type        = string
  default     = "m6i.large"
}

variable "lightsail_bundle_id" {
  description = "Lightsail bundle (size) for the compose-stack instance. Fixed-price (ADR-0001)."
  type        = string
  default     = "large_2_0" # ~4 vCPU / 8 GB — enough for the synthetic demo stack
}

variable "lightsail_blueprint_id" {
  description = "Lightsail OS blueprint. Ubuntu base; Docker installed via user_data."
  type        = string
  default     = "ubuntu_22_04"
}

# --- Common tags applied to every cloud resource -----------------------------
variable "extra_tags" {
  description = "Additional tags merged onto the standard tag set."
  type        = map(string)
  default     = {}
}
