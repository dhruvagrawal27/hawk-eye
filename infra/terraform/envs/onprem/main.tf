# =============================================================================
# Hawk-Eye — env: onprem (self-hosted open-source mirror) [SCAFFOLD]
# Purpose : Calls the root module with target = onprem. The PRODUCTION target
#           (Part 9.3 / Part 16). On-prem is provisioned by Ansible/Helm/compose;
#           Terraform here records the component swaps (Part 26.4). RETAINED.
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# Plan-only, no creds. NEVER `apply`.
# =============================================================================

module "hawk_eye" {
  source = "../../" # the root terraform tree

  target    = "onprem"
  project   = var.project
  env       = var.env
  region    = var.region
  residency = var.residency
}
