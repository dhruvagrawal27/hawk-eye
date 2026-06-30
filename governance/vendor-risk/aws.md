# Vendor Due Diligence — Amazon Web Services (AWS)

> **Workstream:** PLATFORM-38 (vendor / outsourcing risk).
> **Blueprint basis:** Part 34.4 (vendor due diligence, SLAs, audit rights, exit strategy,
> concentration-risk; SBOM linkage), Part 32 (using AWS makes parts of the build **outsourcing**
> under RBI Outsourcing of IT Services Directions 2023), Part 26 (AWS pilot), Part 26.4 (clean
> on-prem migration).
> **Regulators in scope:** RBI Outsourcing of IT Services Directions 2023, RBI ITGRCA MD 2023,
> RBI Cyber Security Framework 2016, DPDP Act 2023, CERT-In v2.0 (SBOM).
> **MOCK status:** the assessment is a human act; the **record** is seeded in the governance DB
> (`vendors` where `name='Amazon Web Services'`).

---

## Vendor record (seeded governance record)

| Field | Value |
|---|---|
| Vendor | **Amazon Web Services** |
| Vendor type | `cloud` (infrastructure) |
| Region of record | `ap-south-1` (Mumbai) — residency **in-India** |
| Status | `assessed` |
| Due diligence | ISO 27001 / SOC 2 reviewed; `ap-south-1` residency confirmed |
| SLA | 99.99% infra; sev-1 1h response |
| Exit strategy | IaC is portable; component-swap to on-prem (migration map) |
| Concentration risk | Mitigated by on-prem migration readiness (Part 26.4) |
| AI clauses | N/A (infra). Data-localization + audit-rights clauses applied |
| SBOM linkage | `ci/security/sbom/` (SPDX + CycloneDX) |
| Evidence record | `vendors` (`name='Amazon Web Services'`) |

> **Deployment note (ADR-0001):** the pilot/demo deployment target is **AWS Lightsail** — a
> deliberate, documented deviation from blueprint Part 26 (EC2-in-VPC). The **production target
> remains on-prem in-India**. See `docs/adr/ADR-0001-ec2-in-vpc.md`. This assessment covers the
> AWS relationship for the synthetic-data, alert-only pilot.

---

## 1. Material-outsourcing classification

| Question | Answer |
|---|---|
| Is this material outsourcing under RBI 2023? | **Yes** — AWS hosts the pilot platform and data plane. |
| Data exposure | **Synthetic data only** in the pilot; no real PII/feeds/creds. Production target is on-prem. |
| Does the Bank retain control & accountability? | **Yes** — outsourcing does not transfer the Bank's regulatory accountability. |

---

## 2. Due-diligence questionnaire (responses)

| # | Area | Question | Response |
|---|---|---|---|
| Q1 | Certifications | ISO 27001 / SOC 2 / PCI-DSS? | ISO 27001 + SOC 2 reviewed; certifications current. |
| Q2 | Data residency | Data kept in India? | `ap-south-1` (Mumbai); residency confirmed for all stateful services. |
| Q3 | Encryption | At rest / in transit? | KMS at rest; mTLS internally; TLS in transit (Part 26.2). |
| Q4 | Access control | Least-privilege, no long-lived keys? | IAM least-privilege roles; no long-lived keys; CloudTrail audit. |
| Q5 | Threat detection | Cloud-side detection & CVE scanning? | GuardDuty + Security Hub + Inspector; WAF on the ALB (Part 26.2). |
| Q6 | Egress control | Outbound restriction? | NAT egress allow-listed to **only** NEAR AI + Groq endpoints; everything else no egress. |
| Q7 | Sub-processors | Subcontractor disclosure? | AWS sub-processor list reviewed; no AI processing of our data by AWS. |
| Q8 | Incident notification | Breach/incident SLA? | Contractual incident notification; feeds our CERT-In 6h workflow. |
| Q9 | Audit rights | Right to audit / inspect? | Audit-rights clause applied; reliance on SOC 2 + right to information. |
| Q10 | Exit | Data return & deletion on exit? | IaC-portable; data export + certified deletion on exit. |
| Q11 | SBOM | Software bill of materials? | Our SBOM at `ci/security/sbom/` (SPDX + CycloneDX, CERT-In v2.0). |

---

## 3. SLA terms

| Metric | Commitment |
|---|---|
| Infrastructure availability | **99.99%** |
| Sev-1 response | **1 hour** |
| Encryption / residency | KMS at rest; `ap-south-1` residency |
| Incident notification | Per contract; routed into our breach-notification workflow (CERT-In 6h) |

---

## 4. Exit strategy

AWS dependence is **convenience, not lock-in** — the stack is all-open-source / self-hostable
and Terraform is parameterised `target = aws | onprem | lightsail`. The component swap (Part 26.4):

`MSK → self-managed Kafka` · `Managed Flink → Flink cluster` · `ElastiCache → Redis` ·
`RDS → PostgreSQL` · `S3 → MinIO` · `KMS → HSM` · `Secrets Manager → HashiCorp Vault` ·
`MWAA → Airflow`. The same IaC builds either environment, so exit is a **rebuild-and-cutover**,
not a re-architecture. Data export + certified deletion on termination.

---

## 5. Concentration-risk assessment (RBI Outsourcing 2023)

| Dimension | Assessment |
|---|---|
| Single-provider dependence | Pilot runs on AWS, but **on-prem migration readiness** (Part 26.4) is the structural mitigation — the Bank can exit to its own data centre. |
| Systemic concentration | The Bank avoids deep managed-service lock-in by staying all-open-source/self-hostable. |
| Residual concentration risk | **Low–Medium**, mitigated by migration readiness and portable IaC. |

---

## 6. AI-specific clauses

AWS is **infrastructure**, so the AI-bias / no-training clauses are largely **N/A** — AWS does
not run our models or train on our data. The **data-localization** and **audit-rights** clauses
from `ai-clause-template.md` are applied. (The AI-specific clauses bind the LLM vendors —
NEAR AI and Groq.)

---

## 7. SBOM linkage
SBOM generated by `ci/security/sbom.sh` (Syft) to `ci/security/sbom/` in **SPDX**
(`sbom.spdx.json`) and **CycloneDX** (`sbom.cdx.json`) — CERT-In v2.0 / RBI software-governance
aligned. CVE scanning via `ci/security/scan.sh` (Grype/Trivy).

---

## 8. Cross-references
- Consolidated register: `governance/vendor-risk/outsourcing-register.md`.
- AI-clause template: `governance/vendor-risk/ai-clause-template.md`.
- NEAR AI / Groq assessments: `governance/vendor-risk/near-ai.md`, `governance/vendor-risk/groq.md`.
- Deployment ADR: `docs/adr/ADR-0001-ec2-in-vpc.md`.
- AI Policy: `governance/docs/ai-policy.md` (BR-2026-014).
