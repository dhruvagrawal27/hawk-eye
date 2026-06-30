# =============================================================================
# Hawk-Eye — Terraform provider & version constraints (root)
# Purpose : Pin Terraform core + provider versions for the parameterized IaC tree.
# Blueprint: Part 26.1 (AWS component mapping), Part 26.4 (target = aws|onprem|lightsail)
# Task     : PLATFORM-7 (Terraform tree)
# -----------------------------------------------------------------------------
# SCAFFOLD: this tree is PLAN-ONLY. It must `terraform init/validate/plan` with
# NO AWS credentials (see backend.tf + provider skip_* flags). Never `apply` —
# real cloud provisioning is out of scope (golden rule 2: on-prem + synthetic).
# Versions pinned from deploy/versions.bom.yaml (terraform 1.9.8).
# =============================================================================

terraform {
  # BOM pin: terraform 1.9.x (patch 1.9.8). >= keeps minor headroom; CI uses 1.9.8.
  required_version = ">= 1.9.0, < 2.0.0"

  required_providers {
    # AWS provider 5.x — used by the aws and lightsail targets only.
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    # null — for on-prem placeholder resources (self-hosted, not cloud-provisioned).
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    # local — for emitting plan-time artifacts / READMEs without external state.
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}
