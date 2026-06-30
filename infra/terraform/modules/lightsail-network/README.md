# Module: `lightsail-network` (PLATFORM-7) — SCAFFOLD · CHOSEN PILOT

Networking for the Lightsail pilot:

- **`aws_lightsail_static_ip`** (+ attachment) — a stable public IP for the demo URL.
- **`aws_lightsail_instance_public_ports`** — least-open firewall: **only HTTPS :443**
  is open to the internet (the dashboard/API behind the in-host reverse proxy) and
  **SSH :22 restricted to admin CIDRs** (never `0.0.0.0/0`). All internal service
  ports (Kafka, Postgres, Redis, etc.) stay private to the host's docker network.

- **Blueprint:** ADR-0001 (Lightsail pilot), Part 26.2 (least-open ingress).
- **SCAFFOLD:** plan-only, never applied.
