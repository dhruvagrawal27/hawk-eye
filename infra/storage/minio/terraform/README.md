# `infra/storage/minio/terraform/` — object-store module stub (DATABASE-1)

> **Plan-only** (no cloud calls). Declares the DATABASE-owned **storage-tier
> contract** — the exact buckets + object-lock/versioning/SSE intent — so
> PLATFORM can include it and apply the AWS S3 equivalent. Mirrors the local
> compose path (`bootstrap_minio.sh`) 1:1.

```bash
terraform -chdir=infra/storage/minio/terraform init -backend=false
terraform -chdir=infra/storage/minio/terraform plan      # no creds needed
```

## Seam
- PLATFORM owns `infra/terraform/modules/s3` (cloud) + `onprem-minio` (marker) and
  the global runtime. This module is **the bucket contract DATABASE publishes**;
  PLATFORM consumes `output.buckets` to provision the real S3/MinIO.
- Do **not** edit PLATFORM's networking or root modules from here.

## AWS swap (1:1)
| Local (MinIO, this stub) | AWS (PLATFORM applies) |
|---|---|
| `mc mb --with-lock models` | `aws_s3_bucket{object_lock_enabled=true}` |
| `mc version enable` | `aws_s3_bucket_versioning{status="Enabled"}` |
| `mc encrypt set sse-s3` (local KMS key) | `…server_side_encryption_configuration{sse_algorithm="aws:kms"}` (SSE-KMS) |
| `mc retention set --default COMPLIANCE` | `aws_s3_bucket_object_lock_configuration{mode="COMPLIANCE"}` |
| least-priv `mc admin policy` | IAM policies (same JSON shape, `policies/*.json`) |

Residency stays **in-India** (`ap-south-1`, Part 9.3). Keys move from the local
MinIO KMS key to **KMS/HSM** custody (PLATFORM owns the key-custody seam).
