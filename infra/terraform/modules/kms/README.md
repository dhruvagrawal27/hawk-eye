# Module: `kms` (PLATFORM-12) — SCAFFOLD

One customer-managed **AWS KMS** key (with annual rotation + alias) used for
encryption-at-rest across S3 (SSE-KMS), RDS, MSK, EBS volumes, and Secrets
Manager / SSM SecureString parameters.

- **Blueprint:** Part 26.1 (Keys → AWS KMS / CloudHSM), Part 26.2 (KMS at rest).
- **Migration (Part 26.4):** `KMS → on-prem HSM` (SoftHSM2 in dev, real PKCS#11
  HSM in prod). See `infra/terraform/migration-map.md` and the `onprem-hsm` module.
- **SCAFFOLD:** plan-only. No key is actually created (never `apply`).

## Inputs
| Name | Description |
|---|---|
| `name_prefix` | `project-env` prefix |
| `tags` | resource tags |

## Outputs
| Name | Description |
|---|---|
| `key_arn` | KMS key ARN (consumed by s3/rds/msk/ec2/secrets) |
| `key_id` | KMS key id |
| `alias_name` | `alias/<prefix>-main` |
