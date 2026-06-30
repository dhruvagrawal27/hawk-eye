# =============================================================================
# Hawk-Eye — RDS module (PostgreSQL, app + governance metadata) [SCAFFOLD]
# Purpose : Managed PostgreSQL for app/case metadata + the governance DB.
#           Private, KMS-encrypted at rest, multi-AZ for HA (Part 30).
# Blueprint: Part 26.1 (App metadata DB → RDS PostgreSQL), Part 26.4 (→ PostgreSQL)
# Task     : PLATFORM-7 (rds)
# =============================================================================

# Subnet group across the private DATA subnets.
resource "aws_db_subnet_group" "main" {
  name       = "${var.name_prefix}-rds-subnets"
  subnet_ids = var.subnet_ids
  tags       = var.tags
}

# SCAFFOLD: Postgres 17.x (BOM pin 17.2). No publicly_accessible; KMS-encrypted.
# The master password is referenced from Secrets Manager at apply time
# (manage_master_user_password = true) — never set inline here.
resource "aws_db_instance" "main" {
  identifier     = "${var.name_prefix}-pg"
  engine         = "postgres"
  engine_version = "17.2" # BOM pin
  instance_class = var.instance_class

  allocated_storage     = 50
  max_allocated_storage = 200
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_name  = "hawkeye"
  username = "hawkeye_admin"
  # No password in TF — RDS-managed master secret stored in Secrets Manager.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  multi_az               = true  # HA (Part 30)
  publicly_accessible    = false # private only — no internet exposure

  backup_retention_period   = 7
  deletion_protection       = true
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name_prefix}-pg-final"

  # Audit hooks: export Postgres logs to CloudWatch.
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = var.tags
}
