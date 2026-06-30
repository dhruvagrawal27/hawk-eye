# =============================================================================
# Hawk-Eye — Security module (WAF + GuardDuty + SecurityHub + Inspector + CloudTrail) [SCAFFOLD]
# Purpose : Cloud-native threat detection + CVE scanning + cloud-side audit.
# Blueprint: Part 26.2 (WAF on ALB; GuardDuty + Security Hub + Inspector; CloudTrail),
#            Part 19.5 (CVE/vuln scanning)
# Task     : PLATFORM-7 (security)
# -----------------------------------------------------------------------------
# IMPORTANT WIRING NOTES:
#  * Inspector findings FEED the PLATFORM-22 vulnerability tracker (CVE management).
#  * CloudTrail is the CLOUD-SIDE audit trail (the app keeps its own WORM audit too).
# =============================================================================

# --- AWS WAFv2 web ACL (regional, attached to the ALB) -----------------------
resource "aws_wafv2_web_acl" "main" {
  name        = "${var.name_prefix}-waf"
  description = "WAF for the public ALB — managed rule groups (OWASP-style)."
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # AWS managed common rule set (SQLi/XSS/etc.).
  rule {
    name     = "AWSManagedCommon"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-common"
      sampled_requests_enabled   = true
    }
  }

  # Known-bad-inputs managed rule set.
  rule {
    name     = "AWSManagedKnownBadInputs"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-knownbad"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name_prefix}-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

# Associate the WAF with the ALB (the only public ingress).
resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}

# --- GuardDuty (threat detection) --------------------------------------------
# Migration (Part 26.4): GuardDuty -> Wazuh + Suricata on-prem.
resource "aws_guardduty_detector" "main" {
  enable = true
  tags   = var.tags
}

# --- Security Hub (posture aggregation) --------------------------------------
# Migration: Security Hub -> OpenSearch SIEM on-prem.
resource "aws_securityhub_account" "main" {}

# --- Inspector v2 (CVE / vulnerability scanning) -----------------------------
# Inspector findings FEED the PLATFORM-22 vuln tracker. Migration: Inspector ->
# Trivy/Grype internal mirror on-prem.
resource "aws_inspector2_enabler" "main" {
  # 12-digit account id. Placeholder default keeps validate/plan credential-free
  # (no aws_caller_identity API call). Set the real account id at apply time.
  account_ids    = [var.account_id]
  resource_types = ["EC2", "ECR"]
}

# --- CloudTrail (cloud-side audit) -------------------------------------------
# Writes to the WORM S3 audit bucket (COMPLIANCE object-lock). This is the
# CLOUD-SIDE audit trail; the application keeps its own immutable audit log too.
# Migration: CloudTrail -> WORM audit log on-prem.
resource "aws_cloudtrail" "main" {
  name                          = "${var.name_prefix}-trail"
  s3_bucket_name                = var.trail_bucket_id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true # tamper-evident
  kms_key_id                    = var.kms_key_arn
  tags                          = var.tags
}
