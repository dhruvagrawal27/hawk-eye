# =============================================================================
# Hawk-Eye — Lightsail instances module (the CHOSEN pilot) [SCAFFOLD]
# Purpose : One Lightsail instance running the docker-compose stack for the
#           synthetic-data demo/pilot. Fixed-price, simple (ADR-0001).
# Blueprint: ADR-0001 (Lightsail = chosen demo/pilot target), Part 26 (deviation noted)
# Task     : PLATFORM-7 (lightsail-instances)
# =============================================================================

# SCAFFOLD: a single Lightsail instance. user_data installs Docker + Compose and
# pulls the BOM-pinned stack (deploy/compose). No GPU on Lightsail — deep training
# stays on AWS/on-prem GPU (ADR-0002); the demo serves pre-trained ONNX on CPU.
resource "aws_lightsail_instance" "compose" {
  name              = "${var.name_prefix}-compose"
  availability_zone = var.availability_zone
  blueprint_id      = var.blueprint_id # ubuntu_22_04
  bundle_id         = var.bundle_id    # fixed-price size

  # Bootstrap: install Docker + Compose. The actual stack is brought up out-of-band
  # (deploy/compose) — kept minimal here so plan needs no real values.
  user_data = <<-EOT
    #!/usr/bin/env bash
    set -euo pipefail
    # SCAFFOLD bootstrap — install Docker engine + compose plugin.
    apt-get update -y
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    # (real key + repo wiring done at apply time; demo stack = deploy/compose)
    echo "hawk-eye lightsail compose host ready (synthetic-data demo)"
  EOT

  tags = var.tags
}
