# =============================================================================
# Hawk-Eye — MWAA module (Amazon Managed Workflows for Apache Airflow) [SCAFFOLD]
# Purpose : Orchestration (training/retrain/ETL DAGs). Private webserver, KMS-
#           encrypted, DAGs sourced from the S3 artifacts bucket.
# Blueprint: Part 26.1 (Orchestration → MWAA), Part 26.4 (MWAA → self-hosted Airflow)
# Task     : PLATFORM-7 (mwaa)
# =============================================================================

# SCAFFOLD: Airflow 2.10.x (BOM pin 2.10.4). PRIVATE_ONLY webserver (no public
# internet), VPC-attached, DAGs from S3, KMS-encrypted.
resource "aws_mwaa_environment" "main" {
  name                  = "${var.name_prefix}-airflow"
  airflow_version       = var.airflow_version
  environment_class     = var.environment_class
  execution_role_arn    = var.execution_role_arn
  kms_key               = var.kms_key_arn
  webserver_access_mode = "PRIVATE_ONLY" # no public webserver — reached via ALB/VPN only

  source_bucket_arn = var.source_bucket_arn
  dag_s3_path       = var.dag_s3_path

  network_configuration {
    subnet_ids         = slice(var.subnet_ids, 0, 2) # MWAA requires exactly 2 subnets
    security_group_ids = [var.security_group_id]
  }

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "INFO"
    }
    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }
    task_logs {
      enabled   = true
      log_level = "INFO"
    }
    webserver_logs {
      enabled   = true
      log_level = "INFO"
    }
    worker_logs {
      enabled   = true
      log_level = "INFO"
    }
  }

  tags = var.tags
}
