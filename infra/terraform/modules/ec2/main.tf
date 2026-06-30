# =============================================================================
# Hawk-Eye — EC2 module (ClickHouse on gp3 + serving + Keycloak) [SCAFFOLD]
# Purpose : Three private EC2 hosts: ClickHouse (analytics store, gp3 EBS),
#           model serving (ONNX/Triton CPU stub), Keycloak (OIDC).
# Blueprint: Part 26.1 (ClickHouse/serving/Keycloak on EC2), Part 26.4 (→ self-hosted)
# Task     : PLATFORM-7 (ec2)
# -----------------------------------------------------------------------------
# NOTE: AMI id is a *variable* (not a data-source lookup) so `plan` needs no AWS
# API call / creds. Replace with a real region-matched AMI at apply time.
# =============================================================================

# --- ClickHouse analytics node (gp3 EBS, KMS-encrypted) ----------------------
resource "aws_instance" "clickhouse" {
  ami                    = var.ami_id
  instance_type          = var.clickhouse_instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.iam_instance_profile

  associate_public_ip_address = false # private only

  root_block_device {
    volume_type = "gp3"
    volume_size = 50
    encrypted   = true
    kms_key_id  = var.kms_key_arn
  }

  # Dedicated gp3 data volume for ClickHouse parts.
  ebs_block_device {
    device_name = "/dev/sdf"
    volume_type = "gp3"
    volume_size = 500
    iops        = 6000
    throughput  = 250
    encrypted   = true
    kms_key_id  = var.kms_key_arn
  }

  metadata_options {
    http_tokens   = "required" # IMDSv2 only (Part 19 hardening)
    http_endpoint = "enabled"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-clickhouse", role = "analytics" })
}

# --- Model serving node (ONNX/Triton CPU stub) -------------------------------
resource "aws_instance" "serving" {
  ami                    = var.ami_id
  instance_type          = var.app_instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.iam_instance_profile

  associate_public_ip_address = false

  root_block_device {
    volume_type = "gp3"
    volume_size = 50
    encrypted   = true
    kms_key_id  = var.kms_key_arn
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-serving", role = "model-serving" })
}

# --- Keycloak node (OIDC/OAuth2 identity) ------------------------------------
resource "aws_instance" "keycloak" {
  ami                    = var.ami_id
  instance_type          = var.app_instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.iam_instance_profile

  associate_public_ip_address = false

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
    encrypted   = true
    kms_key_id  = var.kms_key_arn
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-keycloak", role = "identity" })
}
