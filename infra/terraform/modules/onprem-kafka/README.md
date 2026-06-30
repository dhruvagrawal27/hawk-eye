# Module: `onprem-kafka` (PLATFORM-7) — SCAFFOLD · placeholder

Records the **self-hosted Kafka** component for the **on-prem** target
(the production target, Part 9.3 / Part 16).

- **Self-hosted equivalent:** Apache Kafka 3.8.1 (KRaft) (`apache/kafka:3.8.1`)
- **Migration (Part 26.4):** MSK -> self-managed Kafka
- **Why a placeholder:** on-prem is **not** cloud-provisioned by Terraform — it is
  brought up by Ansible / Helm / docker-compose (`deploy/`, `ops/`). This module
  is a `null_resource` marker so the on-prem target `plan`s cleanly and the
  component identity + swap source are recorded in state/outputs.
- **SCAFFOLD:** plan-only, never applied.
