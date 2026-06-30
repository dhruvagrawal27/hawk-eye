# =============================================================================
# Hawk-Eye — Lightsail network module (static IP + least-open public ports) [SCAFFOLD]
# Purpose : Static IP for the demo instance + the minimal public firewall ports.
# Blueprint: ADR-0001 (Lightsail pilot), Part 26.2 (least-open ingress)
# Task     : PLATFORM-7 (lightsail-network)
# =============================================================================

# Static IP so the demo URL is stable.
resource "aws_lightsail_static_ip" "demo" {
  name = "${var.name_prefix}-static-ip"
}

resource "aws_lightsail_static_ip_attachment" "demo" {
  static_ip_name = aws_lightsail_static_ip.demo.name
  instance_name  = var.instance_name
}

# Least-open public ports. ONLY HTTPS (443) and SSH-from-admin are exposed; the
# many internal service ports (Kafka, Postgres, etc.) stay private to the host's
# docker network — never published to the internet.
resource "aws_lightsail_instance_public_ports" "demo" {
  instance_name = var.instance_name

  # HTTPS — the dashboard / API behind the in-host reverse proxy.
  port_info {
    protocol  = "tcp"
    from_port = 443
    to_port   = 443
  }

  # SSH — restricted to the admin CIDR (not 0.0.0.0/0). Tighten at apply time.
  port_info {
    protocol  = "tcp"
    from_port = 22
    to_port   = 22
    cidrs     = var.ssh_admin_cidrs
  }
}
