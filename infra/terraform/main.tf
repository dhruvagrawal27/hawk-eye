# =============================================================================
# Hawk-Eye — Root composition (target-conditional module wiring)
# Purpose : Instantiate the right module set for var.target (aws|onprem|lightsail).
# Blueprint: Part 26.1 (AWS components), Part 26.2 (security services), Part 26.4
#            (on-prem mirror), ADR-0001 (lightsail = chosen pilot target).
# Task     : PLATFORM-7
# -----------------------------------------------------------------------------
# Pattern: each module is gated by `count = var.target == "<t>" ? 1 : 0` so only
# the selected target's resources appear in the plan. SCAFFOLD throughout —
# plan-only, never applied.
# =============================================================================

locals {
  is_aws       = var.target == "aws"
  is_onprem    = var.target == "onprem"
  is_lightsail = var.target == "lightsail"

  name_prefix = "${var.project}-${var.env}"

  common_tags = merge(
    {
      Project          = var.project
      Environment      = var.env
      "data-residency" = var.residency
      region           = var.region
      DeploymentTarget = var.target
      Scaffold         = "true"
    },
    var.extra_tags,
  )
}

# =============================================================================
# TARGET: aws  — EC2-in-VPC + managed services (Part 26.1) — RETAINED scale path
# =============================================================================

# --- Foundation: KMS keys, network (VPC), IAM least-privilege ----------------
module "kms" {
  source = "./modules/kms"
  count  = local.is_aws ? 1 : 0

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

module "network" {
  source = "./modules/network"
  count  = local.is_aws ? 1 : 0

  name_prefix            = local.name_prefix
  vpc_cidr               = var.vpc_cidr
  azs                    = var.azs
  egress_allowlist_fqdns = var.egress_allowlist_fqdns
  tags                   = local.common_tags
}

module "iam" {
  source = "./modules/iam"
  count  = local.is_aws ? 1 : 0

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

# --- Secrets (NAMES only) ----------------------------------------------------
module "secrets" {
  source = "./modules/secrets"
  count  = local.is_aws ? 1 : 0

  name_prefix  = local.name_prefix
  secret_names = var.secret_names
  kms_key_arn  = local.is_aws ? module.kms[0].key_arn : null
  tags         = local.common_tags
}

# --- Data plane: MSK (Kafka), Managed Flink, ElastiCache (Redis) -------------
module "msk" {
  source = "./modules/msk"
  count  = local.is_aws ? 1 : 0

  name_prefix       = local.name_prefix
  subnet_ids        = local.is_aws ? module.network[0].data_subnet_ids : []
  security_group_id = local.is_aws ? module.network[0].data_sg_id : null
  kms_key_arn       = local.is_aws ? module.kms[0].key_arn : null
  tags              = local.common_tags
}

module "flink" {
  source = "./modules/flink"
  count  = local.is_aws ? 1 : 0

  name_prefix        = local.name_prefix
  subnet_ids         = local.is_aws ? module.network[0].compute_subnet_ids : []
  security_group_id  = local.is_aws ? module.network[0].compute_sg_id : null
  service_role_arn   = local.is_aws ? module.iam[0].flink_role_arn : null
  artifact_bucket_id = local.is_aws ? module.s3[0].artifacts_bucket_id : null
  tags               = local.common_tags
}

module "elasticache" {
  source = "./modules/elasticache"
  count  = local.is_aws ? 1 : 0

  name_prefix       = local.name_prefix
  subnet_ids        = local.is_aws ? module.network[0].data_subnet_ids : []
  security_group_id = local.is_aws ? module.network[0].data_sg_id : null
  tags              = local.common_tags
}

# --- App/analytics: EC2 (ClickHouse + serving + keycloak), RDS (Postgres) ----
module "ec2" {
  source = "./modules/ec2"
  count  = local.is_aws ? 1 : 0

  name_prefix              = local.name_prefix
  subnet_id                = local.is_aws ? module.network[0].compute_subnet_ids[0] : null
  security_group_id        = local.is_aws ? module.network[0].compute_sg_id : null
  iam_instance_profile     = local.is_aws ? module.iam[0].ec2_instance_profile_name : null
  kms_key_arn              = local.is_aws ? module.kms[0].key_arn : null
  clickhouse_instance_type = var.ec2_clickhouse_instance_type
  app_instance_type        = var.ec2_app_instance_type
  tags                     = local.common_tags
}

module "rds" {
  source = "./modules/rds"
  count  = local.is_aws ? 1 : 0

  name_prefix       = local.name_prefix
  subnet_ids        = local.is_aws ? module.network[0].data_subnet_ids : []
  security_group_id = local.is_aws ? module.network[0].data_sg_id : null
  kms_key_arn       = local.is_aws ? module.kms[0].key_arn : null
  tags              = local.common_tags
}

# --- Object store (S3) + orchestration (MWAA) --------------------------------
module "s3" {
  source = "./modules/s3"
  count  = local.is_aws ? 1 : 0

  name_prefix = local.name_prefix
  kms_key_arn = local.is_aws ? module.kms[0].key_arn : null
  tags        = local.common_tags
}

module "mwaa" {
  source = "./modules/mwaa"
  count  = local.is_aws ? 1 : 0

  name_prefix        = local.name_prefix
  subnet_ids         = local.is_aws ? module.network[0].compute_subnet_ids : []
  security_group_id  = local.is_aws ? module.network[0].compute_sg_id : null
  source_bucket_arn  = local.is_aws ? module.s3[0].artifacts_bucket_arn : null
  execution_role_arn = local.is_aws ? module.iam[0].mwaa_role_arn : null
  kms_key_arn        = local.is_aws ? module.kms[0].key_arn : null
  tags               = local.common_tags
}

# --- Edge: ALB (the ONLY public ingress) -------------------------------------
module "alb" {
  source = "./modules/alb"
  count  = local.is_aws ? 1 : 0

  name_prefix       = local.name_prefix
  vpc_id            = local.is_aws ? module.network[0].vpc_id : null
  public_subnet_ids = local.is_aws ? module.network[0].public_subnet_ids : []
  security_group_id = local.is_aws ? module.network[0].alb_sg_id : null
  tags              = local.common_tags
}

# --- Cloud security services (Part 26.2) -------------------------------------
# WAF (on ALB) + GuardDuty + Security Hub + Inspector + CloudTrail.
module "security" {
  source = "./modules/security"
  count  = local.is_aws ? 1 : 0

  name_prefix     = local.name_prefix
  alb_arn         = local.is_aws ? module.alb[0].alb_arn : null
  trail_bucket_id = local.is_aws ? module.s3[0].audit_bucket_id : null
  kms_key_arn     = local.is_aws ? module.kms[0].key_arn : null
  tags            = local.common_tags
}

# =============================================================================
# TARGET: onprem — self-hosted open-source mirror (Part 26.4) — RETAINED
# Lighter modules: null_resource/local placeholders documenting the swap. These
# resources are NOT cloud-provisioned (on-prem is provisioned by Ansible/Helm).
# =============================================================================

module "onprem_kafka" {
  source      = "./modules/onprem-kafka"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_flink" {
  source      = "./modules/onprem-flink"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_redis" {
  source      = "./modules/onprem-redis"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_postgres" {
  source      = "./modules/onprem-postgres"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_minio" {
  source      = "./modules/onprem-minio"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_airflow" {
  source      = "./modules/onprem-airflow"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_vault" {
  source       = "./modules/onprem-vault"
  count        = local.is_onprem ? 1 : 0
  name_prefix  = local.name_prefix
  secret_names = var.secret_names
}

module "onprem_hsm" {
  source      = "./modules/onprem-hsm"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

module "onprem_keycloak" {
  source      = "./modules/onprem-keycloak"
  count       = local.is_onprem ? 1 : 0
  name_prefix = local.name_prefix
}

# =============================================================================
# TARGET: lightsail — the CHOSEN demo/pilot (ADR-0001)
# A single Lightsail instance runs the docker-compose stack; static IP + the
# minimal public ports. Fixed-price, simple, synthetic-data demo.
# =============================================================================

module "lightsail_instances" {
  source = "./modules/lightsail-instances"
  count  = local.is_lightsail ? 1 : 0

  name_prefix       = local.name_prefix
  availability_zone = var.azs[0]
  bundle_id         = var.lightsail_bundle_id
  blueprint_id      = var.lightsail_blueprint_id
  tags              = local.common_tags
}

module "lightsail_network" {
  source = "./modules/lightsail-network"
  count  = local.is_lightsail ? 1 : 0

  name_prefix   = local.name_prefix
  instance_name = local.is_lightsail ? module.lightsail_instances[0].instance_name : null
}
