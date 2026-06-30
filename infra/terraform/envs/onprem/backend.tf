# =============================================================================
# Hawk-Eye — env: onprem — local backend + credential-free provider [SCAFFOLD]
# Purpose : Local state + dummy AWS provider so this env plans with NO creds.
#           (The aws provider is still declared because the root tree references
#           it; the on-prem target instantiates only null/local resources.)
# Task     : PLATFORM-7
# =============================================================================

terraform {
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 5.0" }
    null  = { source = "hashicorp/null", version = "~> 3.2" }
    local = { source = "hashicorp/local", version = "~> 2.5" }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "mock-access-key-DO-NOT-USE"
  secret_key                  = "mock-secret-key-DO-NOT-USE"
  skip_credentials_validation = true
  skip_requesting_account_id  = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
}
