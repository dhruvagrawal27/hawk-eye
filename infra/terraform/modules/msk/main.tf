# =============================================================================
# Hawk-Eye — MSK module (Amazon Managed Streaming for Apache Kafka) [SCAFFOLD]
# Purpose : Event ingestion backbone. Private, KMS-encrypted, TLS in transit.
# Blueprint: Part 26.1 (Ingestion → Amazon MSK), Part 26.4 (MSK → self-managed Kafka)
# Task     : PLATFORM-7 (msk)
# =============================================================================

# SCAFFOLD: Kafka 3.8.x (BOM pin 3.8.1). One broker per AZ. Encryption at rest
# (KMS CMK) + TLS in transit. Private subnets only.
resource "aws_msk_cluster" "main" {
  cluster_name           = "${var.name_prefix}-msk"
  kafka_version          = var.kafka_version # BOM pin family 3.8.x; MSK-supported patch
  number_of_broker_nodes = length(var.subnet_ids)

  broker_node_group_info {
    instance_type   = var.broker_instance_type
    client_subnets  = var.subnet_ids
    security_groups = [var.security_group_id]

    storage_info {
      ebs_storage_info {
        volume_size = 100 # GB gp3-backed broker storage
      }
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = var.kms_key_arn
    encryption_in_transit {
      client_broker = "TLS" # TLS only; no plaintext
      in_cluster    = true
    }
  }

  # Open monitoring -> Prometheus (PLATFORM observability stack).
  open_monitoring {
    prometheus {
      jmx_exporter {
        enabled_in_broker = true
      }
      node_exporter {
        enabled_in_broker = true
      }
    }
  }

  tags = var.tags
}
