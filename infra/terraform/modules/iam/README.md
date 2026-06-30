# Module: `iam` (PLATFORM-7) — SCAFFOLD

Least-privilege **IAM roles** for the AWS pilot — assumed via the STS trust model
(service principals + EC2 instance profile). **No IAM users, no long-lived access
keys** (Part 26.2).

| Role | Trust | Purpose |
|---|---|---|
| `ec2-role` (+ instance profile) | `ec2.amazonaws.com` | ClickHouse / serving / Keycloak hosts; read own secrets, write own logs |
| `flink-role` | `kinesisanalytics.amazonaws.com` | Managed Service for Apache Flink |
| `mwaa-role` | `airflow.amazonaws.com` | MWAA execution |

Inline policies scope `secretsmanager:GetSecretValue` / `ssm:GetParameter` and log
writes to `<prefix>-*` ARNs only. Tighten resource ARNs further at apply time.

**Migration (Part 26.4):** on-prem replaces IAM roles with SPIFFE/SPIRE workload
identity + Vault auth (no cloud STS). SCAFFOLD: plan-only, never applied.
