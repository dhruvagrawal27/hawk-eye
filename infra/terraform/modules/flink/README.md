# Module: `flink` (PLATFORM-7) — SCAFFOLD

**Amazon Managed Service for Apache Flink** (runtime **FLINK-1_20**, BOM pin 1.20.0)
for stateful streaming / CEP (L1 rules, L2 feature engineering).

- VPC-attached (private compute subnets only); app package pulled from the S3
  artifacts bucket (published by DATA/ML); default checkpointing + Prometheus-grade
  app metrics.
- **Blueprint:** Part 26.1 (Stream processing → Managed Service for Apache Flink).
- **Migration (Part 26.4):** `Managed Flink → self-hosted Flink 1.20.0 cluster`
  (JobManager/TaskManager). Same job JAR. See `migration-map.md`.
- **SCAFFOLD:** plan-only, never applied.
