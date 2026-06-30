# Module: `security` (PLATFORM-7) — SCAFFOLD

Cloud-native security services for the AWS pilot (Part 26.2, Part 19.5).

| Resource | Purpose | On-prem equivalent (Part 26.4) |
|---|---|---|
| `aws_wafv2_web_acl` (+ ALB association) | WAF on the public ALB; AWS managed Common + KnownBadInputs rule sets | reverse-proxy WAF / **ModSecurity** |
| `aws_guardduty_detector` | threat detection | **Wazuh + Suricata** |
| `aws_securityhub_account` | security-posture aggregation | **OpenSearch SIEM** |
| `aws_inspector2_enabler` | **CVE / vulnerability scanning** (EC2 + ECR) | **Trivy / Grype** internal mirror |
| `aws_cloudtrail` | cloud-side audit → WORM S3 audit bucket | **WORM audit log** |

**Key wiring notes:**
- **Inspector findings feed the PLATFORM-22 vulnerability tracker** (CVE management
  programme). The two managed-vuln pipelines (cloud Inspector, internal Trivy/Grype)
  converge on the same tracker.
- **CloudTrail is the cloud-side audit trail.** The application keeps its **own**
  immutable WORM audit log independently; CloudTrail captures the AWS-control-plane
  layer. CloudTrail writes to the COMPLIANCE-locked S3 audit bucket with log-file
  validation (tamper-evident).

**SCAFFOLD:** plan-only, never applied.
