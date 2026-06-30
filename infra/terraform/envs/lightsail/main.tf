# =============================================================================
# Hawk-Eye — env: lightsail (the CHOSEN demo/pilot) [SCAFFOLD]
# Purpose : Calls the root module with target = lightsail. The program's chosen
#           pilot target (ADR-0001): a Lightsail instance running the compose stack.
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# Plan-only, no creds. NEVER `apply`.
# =============================================================================

module "hawk_eye" {
  source = "../../" # the root terraform tree

  target    = "lightsail"
  project   = var.project
  env       = var.env
  region    = var.region
  residency = var.residency
}
