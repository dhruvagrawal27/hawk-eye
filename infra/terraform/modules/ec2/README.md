# Module: `ec2` (PLATFORM-7) — SCAFFOLD

Three **private** EC2 hosts (no public IPs, **IMDSv2 required**, **KMS-encrypted gp3
EBS**):

| Host | Type (default) | Role |
|---|---|---|
| `clickhouse` | `r6i.xlarge` | analytics/investigation store; 500 GB gp3 data volume |
| `serving` | `m6i.large` | ONNX/Triton model serving (CPU; ADR-0002) |
| `keycloak` | `m6i.large` | OIDC/OAuth2 identity |

- **AMI is a variable** (`ami-0000…` placeholder) — not a data-source lookup — so
  `plan` runs with no AWS creds. Set a real ap-south-1 AMI at apply time.
- **Blueprint:** Part 26.1 (ClickHouse on EC2 gp3; serving on EC2; Keycloak on EC2).
- **Migration (Part 26.4):** these are already self-hosted open-source — on-prem
  runs the *same* containers (ClickHouse 25.3, Triton/ONNX, Keycloak 25.0.6) on the
  bank's own hosts. See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
