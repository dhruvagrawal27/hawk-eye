# =============================================================================
# Hawk-Eye — Flink module (Amazon Managed Service for Apache Flink) [SCAFFOLD]
# Purpose : Stateful streaming / CEP for feature engineering + rules (L1/L2).
#           Runs in the VPC (private), reads the Flink job artifact from S3.
# Blueprint: Part 26.1 (Stream processing → Managed Service for Apache Flink), 26.4 (→ Flink cluster)
# Task     : PLATFORM-7 (flink)
# =============================================================================

# SCAFFOLD: Managed Flink 1.20.x (BOM pin 1.20.0). VPC-attached, app code pulled
# from the artifacts S3 bucket. The job JAR is published by DATA/ML; here we only
# scaffold the runtime.
resource "aws_kinesisanalyticsv2_application" "main" {
  name                   = "${var.name_prefix}-flink"
  runtime_environment    = var.flink_runtime # e.g. FLINK-1_20
  service_execution_role = var.service_role_arn

  application_configuration {
    application_code_configuration {
      code_content {
        s3_content_location {
          bucket_arn = "arn:aws:s3:::${var.artifact_bucket_id}"
          file_key   = var.application_jar_key
        }
      }
      code_content_type = "ZIPFILE"
    }

    # VPC attach: keep all streaming traffic inside the private compute subnets.
    vpc_configuration {
      subnet_ids         = var.subnet_ids
      security_group_ids = [var.security_group_id]
    }

    flink_application_configuration {
      checkpoint_configuration {
        configuration_type = "DEFAULT"
      }
      monitoring_configuration {
        configuration_type = "DEFAULT"
        log_level          = "INFO"
        metrics_level      = "APPLICATION"
      }
      parallelism_configuration {
        configuration_type = "DEFAULT"
      }
    }
  }

  tags = var.tags
}
