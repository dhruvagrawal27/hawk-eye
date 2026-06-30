# --- security module outputs -------------------------------------------------
output "waf_web_acl_arn" {
  description = "WAFv2 web ACL ARN (associated with the ALB)."
  value       = aws_wafv2_web_acl.main.arn
}

output "guardduty_detector_id" {
  description = "GuardDuty detector id."
  value       = aws_guardduty_detector.main.id
}

output "cloudtrail_arn" {
  description = "CloudTrail trail ARN (cloud-side audit)."
  value       = aws_cloudtrail.main.arn
}

output "inspector_note" {
  description = "Reminder: Inspector findings feed the PLATFORM-22 vuln tracker."
  value       = "inspector2 findings -> PLATFORM-22 CVE/vuln tracker"
}
