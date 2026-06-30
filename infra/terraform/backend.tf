# =============================================================================
# Hawk-Eye — Terraform backend + provider config (root)
# Purpose : LOCAL/mock backend + credential-free AWS provider so the whole tree
#           can `init/validate/plan` with NO AWS account and NO real secrets.
# Blueprint: Part 26.1/26.2, golden rule 2 (no real creds, no internet egress)
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# WHY LOCAL / PLAN-ONLY (intentional SCAFFOLD):
#   * Hawk-Eye is on-prem + synthetic. The AWS/Lightsail modules are a documented
#     SCAFFOLD that must be reviewable (plan output) WITHOUT touching real cloud.
#   * No remote state (no S3/DynamoDB backend) — that would itself need creds.
#   * The aws provider below uses dummy creds + skip_* flags so `plan` resolves
#     without calling STS / IMDS / the account-id endpoint. NEVER run `apply`.
# =============================================================================

terraform {
  # Local state only. State file stays in the working dir; nothing leaves the host.
  backend "local" {
    path = "terraform.tfstate"
  }
}

# --- AWS provider: credential-free, plan-only --------------------------------
# Used by the `aws` and `lightsail` targets. The dummy access/secret keys and the
# skip_* flags let `validate`/`plan` run offline. These are NOT real credentials
# and grant nothing — they only satisfy the provider's config schema.
provider "aws" {
  region = var.region

  # Dummy creds — placeholders so the provider initializes with no real account.
  access_key = "mock-access-key-DO-NOT-USE"
  secret_key = "mock-secret-key-DO-NOT-USE"

  # Skip all live AWS API calls during init/plan (no STS, no IMDS, no account id).
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  # Lets plan proceed for regions/partitions without an online region lookup.
  skip_region_validation = true

  # Standard tags stamped on every taggable resource (residency + project + env).
  default_tags {
    tags = {
      Project          = var.project
      Environment      = var.env
      "data-residency" = var.residency
      region           = var.region
      ManagedBy        = "terraform"
      Scaffold         = "true" # every cloud resource is SCAFFOLD (plan-only)
      DeploymentTarget = var.target
    }
  }
}
