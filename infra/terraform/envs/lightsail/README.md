# env: `lightsail` — the CHOSEN demo/pilot (SCAFFOLD, plan-only)

Calls the root Terraform tree (`../../`) with **`target = lightsail`** — the program's
**chosen pilot target** (see `docs/adr/ADR-0001-ec2-in-vpc.md`). A single Lightsail
instance runs the docker-compose stack; fixed-price, simple, synthetic-data demo.

## Plan (no AWS credentials required — NEVER apply)
```bash
cd infra/terraform/envs/lightsail
terraform init
terraform validate
terraform plan        # 4 resources: instance + static IP (+ attachment) + public ports
```

- **Local backend** — no remote state, no creds.
- The `provider "aws"` here uses dummy creds + `skip_*` flags so `plan` runs offline.
- **SCAFFOLD:** plan-only. Do **not** `terraform apply`.
- Region pinned to `ap-south-1` for data residency (Part 16). No GPU on Lightsail —
  deep training stays on AWS/on-prem GPU (ADR-0002); the demo serves ONNX on CPU.
