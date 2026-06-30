# =============================================================================
# Hawk-Eye — IAM module (least-privilege roles, NO long-lived keys) [SCAFFOLD]
# Purpose : Service roles for EC2, Flink, MWAA assumed via the AWS STS trust model
#           (instance profiles / service principals) — no IAM users, no access keys.
# Blueprint: Part 26.2 (IAM least-privilege, no long-lived keys)
# Task     : PLATFORM-7 (iam)
# =============================================================================

# --- EC2 instance role (ClickHouse / serving / Keycloak hosts) ---------------
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.name_prefix}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = var.tags
}

# Least-privilege inline: read its own secrets + write logs only. No wildcards on
# resources beyond what the scaffold needs; tighten ARNs at apply time.
data "aws_iam_policy_document" "ec2_inline" {
  statement {
    sid       = "ReadRuntimeSecrets"
    actions   = ["secretsmanager:GetSecretValue", "ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:aws:secretsmanager:*:*:secret:${var.name_prefix}-*", "arn:aws:ssm:*:*:parameter/${var.name_prefix}/*"]
  }
  statement {
    sid       = "WriteOwnLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:log-group:/${var.name_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "ec2_inline" {
  name   = "${var.name_prefix}-ec2-inline"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.ec2_inline.json
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.name_prefix}-ec2-profile"
  role = aws_iam_role.ec2.name
  tags = var.tags
}

# --- Managed Flink service role ---------------------------------------------
data "aws_iam_policy_document" "flink_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["kinesisanalytics.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "flink" {
  name               = "${var.name_prefix}-flink-role"
  assume_role_policy = data.aws_iam_policy_document.flink_assume.json
  tags               = var.tags
}

# --- MWAA execution role -----------------------------------------------------
data "aws_iam_policy_document" "mwaa_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["airflow.amazonaws.com", "airflow-env.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "mwaa" {
  name               = "${var.name_prefix}-mwaa-role"
  assume_role_policy = data.aws_iam_policy_document.mwaa_assume.json
  tags               = var.tags
}
