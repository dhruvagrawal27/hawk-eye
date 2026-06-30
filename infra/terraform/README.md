# Hawk-Eye — Terraform (parameterized IaC) — SCAFFOLD, PLAN-ONLY

Single, target-parameterized Terraform tree for the Hawk-Eye platform.

- **Blueprint:** Part 26.1 (AWS component mapping), Part 26.2 (AWS security),
  Part 26.3 (cost-conscious sizing), Part 26.4 (AWS→on-prem migration), Part 16
  (data residency in-India). **Tasks:** PLATFORM-7, PLATFORM-8, PLATFORM-12 (kms).
- **ADR:** `docs/adr/ADR-0001-ec2-in-vpc.md` (Lightsail = chosen pilot).
- **Migration map:** `migration-map.md` (the 8 component swaps + LLM + security).

## The `target` switch

```hcl
variable "target" {}  # aws | onprem | lightsail (validated)
```

| `target` | What it builds | Resources (plan) | Blueprint role |
|---|---|---|---|
| `lightsail` | one Lightsail instance + static IP + ports (compose stack) | ~4 | **chosen demo/pilot** (ADR-0001) |
| `aws` | EC2-in-VPC + MSK/Flink/ElastiCache/RDS/S3/MWAA/ALB + KMS/IAM/Secrets/Network + WAF/GuardDuty/SecurityHub/Inspector/CloudTrail | ~68 | production-shaped pilot / scale-up (**retained**) |
| `onprem` | `null_resource` markers for the 9 self-hosted swaps | ~9 | production target (provisioned by Ansible/Helm/compose) |

Modules are gated by `count = var.target == "<t>" ? 1 : 0`.

## Run it (NO credentials needed — NEVER apply)

```bash
# From the root tree:
cd infra/terraform
terraform init
terraform validate
terraform plan -var 'target=lightsail'   # or aws / onprem

# Or from a pinned env:
cd infra/terraform/envs/lightsail && terraform init && terraform plan
```

- **Local backend** (`backend.tf`) — no remote state.
- **Credential-free provider** — dummy creds + `skip_credentials_validation` /
  `skip_requesting_account_id` / `skip_metadata_api_check` so `plan` runs offline.
- **SCAFFOLD / plan-only:** every cloud resource is tagged `Scaffold = "true"`.
  **Do not `terraform apply`** — real cloud provisioning is out of scope (golden
  rule 2: on-prem + synthetic, no real creds, no internet egress in the running
  system). Validated against Terraform 1.9.8 (BOM pin).

## Layout

```
infra/terraform/
├── versions.tf  variables.tf  main.tf  outputs.tf  backend.tf  migration-map.md
├── modules/
│   ├── (aws)      network iam kms secrets s3 rds elasticache msk flink ec2 mwaa alb security
│   ├── (onprem)   onprem-{kafka,flink,redis,postgres,minio,airflow,vault,hsm,keycloak}
│   └── (lightsail) lightsail-instances  lightsail-network
└── envs/
    ├── aws/  onprem/  lightsail/   (each: main.tf backend.tf variables.tf terraform.tfvars README.md)
```

## Residency & egress invariants (baked in)

- Region forced to `ap-south-1` (variable validation) + `data-residency: in-india`
  tag on every resource (Part 16).
- Data tier has **no internet route**; compute tier egresses **only** via the
  allow-listed NAT to `cloud-api.near.ai` + `api.groq.com` (Part 26.2). See
  `modules/network/README.md` for how FQDN egress is enforced (proxy / DNS firewall).
- Secrets hold **names only**; values are injected out-of-band (golden rule).
