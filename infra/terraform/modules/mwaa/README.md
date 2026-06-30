# Module: `mwaa` (PLATFORM-7) — SCAFFOLD

**Amazon MWAA** (managed **Airflow 2.10.x**, BOM pin 2.10.4) for orchestration
(training/retrain/ETL DAGs).

- **PRIVATE_ONLY** webserver (no public internet — reached via ALB/VPN), VPC-attached
  to exactly 2 compute subnets, **KMS-encrypted**, full logging to CloudWatch, DAGs
  pulled from the S3 artifacts bucket (`airflow/dags`).
- **Blueprint:** Part 26.1 (Orchestration → MWAA).
- **Migration (Part 26.4):** `MWAA → self-hosted Airflow 2.10.4`. Same DAGs. See
  `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
