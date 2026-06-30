# =============================================================================
# Hawk-Eye — env: aws (EC2-in-VPC + managed services) [SCAFFOLD]
# Purpose : Calls the root module with target = aws. The production-shaped pilot
#           / scale-up path (RETAINED). Part 26.1.
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# Plan-only, no creds. See README for the command. NEVER `apply`.
# =============================================================================

module "hawk_eye" {
  source = "../../" # the root terraform tree

  target    = "aws"
  project   = var.project
  env       = var.env
  region    = var.region
  residency = var.residency
}
