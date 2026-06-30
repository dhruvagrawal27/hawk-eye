# env: `aws` — EC2-in-VPC + managed services (SCAFFOLD, plan-only)

Calls the root Terraform tree (`../../`) with **`target = aws`** — the
production-shaped pilot / scale-up path (Part 26.1), **RETAINED** alongside the
chosen Lightsail pilot (ADR-0001).

## Plan (no AWS credentials required — NEVER apply)
```bash
cd infra/terraform/envs/aws
terraform init
terraform validate
terraform plan        # ~68 resources; uses dummy creds + skip_* flags
```

- **Local backend** (`terraform.tfstate` in this dir) — no remote state, no creds.
- The `provider "aws"` here uses dummy creds + `skip_credentials_validation` /
  `skip_requesting_account_id` / `skip_metadata_api_check`, so `plan` runs offline.
- **SCAFFOLD:** plan-only. Do **not** run `terraform apply` — real cloud
  provisioning is out of scope (golden rule 2).
- A harmless `Backend configuration ignored` warning is expected (the root tree is
  itself runnable; here it is called as a child module).

## Values
See `terraform.tfvars`. Region is pinned to `ap-south-1` for data residency (Part 16).
