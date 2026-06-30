# =============================================================================
# Hawk-Eye — env: aws — local backend + credential-free provider [SCAFFOLD]
# Purpose : Local state + dummy AWS provider so this env plans with NO creds.
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# The root module's own provider/backend apply when the root is run directly;
# when consumed here as a child module the env supplies the provider + backend.
# =============================================================================

terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 5.0" }
    null  = { source = "hashicorp/null", version = "~> 3.2" }
    local = { source = "hashicorp/local", version = "~> 2.5" }
  }

  # Local state only — nothing leaves the host (plan-only SCAFFOLD).
  backend "local" {
    path = "terraform.tfstate"
  }
}

# Credential-free AWS provider (dummy creds + skip_* flags). NEVER real creds.
provider "aws" {
  region                      = var.region
  access_key                  = "mock-access-key-DO-NOT-USE"
  secret_key                  = "mock-secret-key-DO-NOT-USE"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
}
