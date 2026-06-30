# Module: `onprem-minio` (PLATFORM-7) — SCAFFOLD · placeholder

Records the **self-hosted MinIO** component for the **on-prem** target
(the production target, Part 9.3 / Part 16).

- **Self-hosted equivalent:** MinIO (S3 API, object-lock/WORM) (`minio/minio:RELEASE.2024-12-18T13-15-44Z`)
- **Migration (Part 26.4):** S3 -> MinIO
- **Why a placeholder:** on-prem is **not** cloud-provisioned by Terraform — it is
  brought up by Ansible / Helm / docker-compose (`deploy/`, `ops/`). This module
  is a `null_resource` marker so the on-prem target `plan`s cleanly and the
  component identity + swap source are recorded in state/outputs.
- **SCAFFOLD:** plan-only, never applied.
