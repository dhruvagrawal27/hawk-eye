# Module: `onprem-hsm` (PLATFORM-7) — SCAFFOLD · placeholder

Records the **self-hosted HSM** component for the **on-prem** target
(the production target, Part 9.3 / Part 16).

- **Self-hosted equivalent:** PKCS#11 HSM (SoftHSM2 in dev) (`softhsm2:2.6.1`)
- **Migration (Part 26.4):** KMS -> HSM
- **Why a placeholder:** on-prem is **not** cloud-provisioned by Terraform — it is
  brought up by Ansible / Helm / docker-compose (`deploy/`, `ops/`). This module
  is a `null_resource` marker so the on-prem target `plan`s cleanly and the
  component identity + swap source are recorded in state/outputs.
- **SCAFFOLD:** plan-only, never applied.
