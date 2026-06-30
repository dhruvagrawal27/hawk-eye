# =============================================================================
# Hawk-Eye — Root outputs (target-aware)
# Purpose : Surface the key identifiers per target for downstream wiring/inspection.
# Blueprint: Part 26.1/26.4
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# All outputs use the [0] index guarded by the module count so they resolve to
# null when their target is not selected (no error on the other two targets).
# =============================================================================

output "target" {
  description = "The deployment target this plan represents."
  value       = var.target
}

output "region" {
  description = "AWS region (data residency, Part 16)."
  value       = var.region
}

output "residency" {
  description = "Data-residency label."
  value       = var.residency
}

# --- AWS target outputs ------------------------------------------------------
output "aws_vpc_id" {
  description = "VPC id (aws target)."
  value       = var.target == "aws" ? module.network[0].vpc_id : null
}

output "aws_alb_dns_name" {
  description = "Public ALB DNS name — the ONLY public ingress (aws target)."
  value       = var.target == "aws" ? module.alb[0].alb_dns_name : null
}

output "aws_kms_key_arn" {
  description = "KMS key ARN for at-rest encryption (aws target)."
  value       = var.target == "aws" ? module.kms[0].key_arn : null
}

output "aws_msk_cluster_arn" {
  description = "MSK (Kafka) cluster ARN (aws target)."
  value       = var.target == "aws" ? module.msk[0].cluster_arn : null
}

output "aws_rds_endpoint" {
  description = "RDS PostgreSQL endpoint (aws target)."
  value       = var.target == "aws" ? module.rds[0].endpoint : null
}

output "aws_s3_artifacts_bucket" {
  description = "S3 artifacts bucket name (aws target)."
  value       = var.target == "aws" ? module.s3[0].artifacts_bucket_id : null
}

output "aws_secret_names" {
  description = "Names (not values) of the runtime secrets registered (aws target)."
  value       = var.target == "aws" ? module.secrets[0].secret_names : null
}

# --- on-prem target outputs --------------------------------------------------
output "onprem_components" {
  description = "Self-hosted components scaffolded for the on-prem target."
  value = var.target == "onprem" ? {
    kafka    = module.onprem_kafka[0].component
    flink    = module.onprem_flink[0].component
    redis    = module.onprem_redis[0].component
    postgres = module.onprem_postgres[0].component
    minio    = module.onprem_minio[0].component
    airflow  = module.onprem_airflow[0].component
    vault    = module.onprem_vault[0].component
    hsm      = module.onprem_hsm[0].component
    keycloak = module.onprem_keycloak[0].component
  } : null
}

# --- lightsail target outputs ------------------------------------------------
output "lightsail_instance_name" {
  description = "Lightsail instance running the compose stack (lightsail target)."
  value       = var.target == "lightsail" ? module.lightsail_instances[0].instance_name : null
}

output "lightsail_static_ip" {
  description = "Lightsail static IP attached to the demo instance (lightsail target)."
  value       = var.target == "lightsail" ? module.lightsail_network[0].static_ip_name : null
}
