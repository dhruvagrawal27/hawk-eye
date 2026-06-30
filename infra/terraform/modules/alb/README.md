# Module: `alb` (PLATFORM-7) — SCAFFOLD

The internet-facing **Application Load Balancer** — the **single public ingress**
(Part 26.2). Everything else in the VPC is private.

- HTTP :80 → 301 redirect to HTTPS; HTTPS :443 with a **TLS 1.3** policy and an ACM
  cert (placeholder ARN for plan; real ARN at apply). Forwards to the backend target
  group (`:8000`, `/healthz`). `drop_invalid_header_fields` + deletion protection on.
- **WAF** is attached to this ALB by the `security` module.
- **Blueprint:** Part 26.1 (App/API behind ALB), Part 26.2 (only the ALB is public).
- **Migration (Part 26.4):** on-prem replaces the ALB with a reverse proxy
  (nginx/Envoy) + ModSecurity WAF. See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
