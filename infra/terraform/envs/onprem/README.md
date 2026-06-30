# env: `onprem` — self-hosted open-source mirror (SCAFFOLD, plan-only)

Calls the root Terraform tree (`../../`) with **`target = onprem`** — the **production
target** (Part 9.3 / Part 16). On-prem is **not** cloud-provisioned by Terraform; it is
brought up by Ansible / Helm / docker-compose (`deploy/`, `ops/`). This target's
Terraform records the **component swaps** (Part 26.4) as `null_resource` markers so the
plan is clean and the swap map is in state/outputs.

## Plan (no credentials required — NEVER apply)
```bash
cd infra/terraform/envs/onprem
terraform init
terraform validate
terraform plan        # 9 null_resource markers (kafka/flink/redis/postgres/minio/airflow/vault/hsm/keycloak)
```

- **Local backend** — no remote state, no creds.
- The `aws` provider is declared (the shared root references it) but the on-prem
  target instantiates only `null`/`local` resources, so no AWS API is touched.
- **SCAFFOLD:** plan-only. See `migration-map.md` for the full AWS→on-prem swap table.
