# Hawk-Eye — AWS → On-Prem Migration Map

- **Purpose:** the component-swap table that makes the AWS pilot migrate cleanly back
  to the on-prem production target — by design, a swap, not a rewrite.
- **Blueprint:** Part 26.4 (clean AWS→on-prem migration path); Part 9.3 / Part 16
  (on-prem in-India is the production target); Part 25 / Part 26.4 (the LLM swap);
  Part 26.2 / Part 19.5 (the security-service swaps).
- **Task:** PLATFORM-8.
- **Terraform:** the same root tree builds either environment via
  `var.target = aws | onprem | lightsail` (see `infra/terraform/`). The on-prem
  modules are `null_resource` markers because on-prem is provisioned by
  Ansible/Helm/compose (`deploy/`, `ops/`), not cloud APIs.

> **Why this is lock-in-free.** Every AWS managed service in the pilot is a
> *convenience wrapper around an open-source engine we already self-host*. The
> versions are pinned identically on both sides (see `deploy/versions.bom.yaml`), so
> contracts (topics, schemas, DDL, DAGs, model artifacts) port unchanged.

---

## A. Core data-plane / platform swaps (the 8 component swaps, Part 26.4)

| # | AWS (pilot) | On-prem (production) | Pinned version (BOM) | What ports over unchanged | TF module (aws → onprem) |
|---|---|---|---|---|---|
| 1 | **Amazon MSK** | **Self-managed Apache Kafka** (KRaft) | 3.8.1 | Topics (`infra/kafka/topics.yaml`), producers/consumers, schema-registry contracts | `msk` → `onprem-kafka` |
| 2 | **Amazon Managed Service for Apache Flink** | **Self-hosted Flink cluster** (JobManager/TaskManager) | 1.20.0 | The streaming job JAR, checkpoint config, state | `flink` → `onprem-flink` |
| 3 | **ElastiCache for Redis** | **Self-hosted Redis** | 7.4.1 | Feast online-store contract, keys, client code | `elasticache` → `onprem-redis` |
| 4 | **Amazon RDS for PostgreSQL** | **Self-hosted PostgreSQL** | 17.2 | App + governance DB schema/DDL (owned by DATABASE), connection strings | `rds` → `onprem-postgres` |
| 5 | **Amazon S3** (SSE-KMS, versioned, object-lock) | **MinIO** (S3 API; object-lock / WORM) | RELEASE.2024-12-18 | Bucket layout, S3 client SDK, model/dataset paths | `s3` → `onprem-minio` |
| 6 | **AWS KMS** (CMK) | **HSM** (PKCS#11; SoftHSM2 in dev) | softhsm2 2.6.1 | Envelope-encryption interface, key aliases | `kms` → `onprem-hsm` |
| 7 | **AWS Secrets Manager / SSM** | **HashiCorp Vault** | 1.18 | The 3 secret **names** (`NEAR_AI_API_KEY`, `GROQ_API_KEY`, `PII_HMAC_KEY`); Vault KV path `secret/hawk-eye/<name>` | `secrets` → `onprem-vault` |
| 8 | **Amazon MWAA** (Managed Airflow) | **Self-hosted Apache Airflow** | 2.10.4 | The DAGs (`airflow/dags`), operators, connections | `mwaa` → `onprem-airflow` |

**Also self-hosted on EC2 in the pilot (already open-source, identical on-prem):**
ClickHouse 25.3 (analytics store), Triton/ONNX serving (CPU; ADR-0002), Keycloak
25.0.6 (OIDC). These are the *same* containers on both sides — no managed-service
indirection to unwind. (`ec2` module → on-prem hosts; Keycloak tracked as
`onprem-keycloak`.)

---

## B. The LLM swap (the cross-border angle, Part 25 / Part 26.4)

This is the swap that turns the *one* remaining outbound dependency into a fully
on-prem, air-gapped path.

| Aspect | AWS pilot | On-prem production |
|---|---|---|
| **Provider** | External **NEAR AI** confidential-compute gateway (+ Groq fallback) over the allow-listed NAT egress | The bank's **own H100 / H200** confidential-compute node |
| **TEE** | Provider-side TEE; attestation is the trust anchor | **Intel TDX** on the bank's GPU node — same attestation flow |
| **Model** | Hosted model behind the gateway | **gpt-oss-120b** running locally |
| **Interface** | OpenAI-compatible API | **Same OpenAI-compatible API** — client code unchanged |
| **PII** | Tokenized/hashed **before** egress (Part 25.3); raw PII never leaves | No egress at all — fully air-gapped; tokenization still applied defence-in-depth |
| **Residency (Part 16 / DPDP)** | Documented cross-border transfer, mitigated by tokenization + TEE | **Full in-India residency** — no transfer occurs |
| **Egress allow-list** | NAT → `cloud-api.near.ai` + `api.groq.com` ONLY | Allow-list becomes **empty**; the air-gap is total |

**Net effect:** the LLM narrative/EDD gateway migrates without touching application
code — same interface, same attestation guarantees — and the cross-border DPDP
exposure disappears because nothing leaves India (the preferred end-state, Part 28.1).

---

## C. Security-service on-prem equivalents (Part 26.2 / Part 19.5)

The cloud-native security stack maps to self-hosted open-source equivalents. Both
sides feed the **same** downstream programmes (vuln tracker PLATFORM-22, the SIEM,
the immutable audit trail).

| AWS security service | Role | On-prem equivalent | Notes |
|---|---|---|---|
| **AWS WAF** (on the ALB) | L7 web firewall | **Reverse-proxy WAF / ModSecurity** (nginx/Envoy + ModSecurity/Coraza) | Same OWASP-style rule intent in front of the only public ingress |
| **Amazon GuardDuty** | threat detection (network/behaviour) | **Wazuh + Suricata** | Host IDS (Wazuh) + network IDS (Suricata) |
| **AWS Security Hub** | security-posture aggregation | **OpenSearch SIEM** | Central findings/log correlation |
| **Amazon Inspector** (v2) | **CVE / vulnerability scanning** (EC2 + ECR) | **Trivy / Grype** internal mirror | Both pipelines **feed the PLATFORM-22 vuln tracker** (single CVE backlog) |
| **AWS CloudTrail** | cloud-side control-plane audit | **WORM audit log** | On-prem keeps an immutable WORM audit log; the app's own audit trail exists on both sides regardless |

**Wiring invariants preserved across the swap:**
- **Inspector → Trivy/Grype** findings both land in the **PLATFORM-22** vulnerability
  tracker; the CVE-management programme is identical either side.
- **CloudTrail → WORM audit log** is the *infrastructure/control-plane* audit. The
  **application's own immutable audit trail** (alerts, dispositions, investigator
  actions — "watch the watchers", Part 19) is independent and present in both
  environments.
- **mTLS internally**, **least-privilege identity** (IAM roles → SPIFFE/SPIRE + Vault
  auth), and the **egress air-gap** all carry over.

---

## D. Migration mechanics (summary)

1. **Stand up on-prem** with the same BOM versions (`deploy/versions.bom.yaml`) via
   `deploy/` (compose/helm) + `ops/` (ansible). `terraform -chdir=infra/terraform/envs/onprem`
   records the swap markers.
2. **Re-point contracts** (topics, schema-registry, DDL, DAGs, model paths) — they are
   identical, so this is configuration, not code.
3. **Migrate the LLM** to the on-prem TDX node running gpt-oss-120b; swap the gateway
   base-URL; empty the egress allow-list.
4. **Swap the security stack** (ModSecurity / Wazuh+Suricata / OpenSearch / Trivy+Grype
   / WORM audit) and re-wire findings into the same PLATFORM-22 tracker + SIEM.
5. **Verify**: synthetic end-to-end run, residency check (all in-India), air-gap check
   (no egress), audit-trail continuity.

> **Golden rules upheld throughout:** alert-only (no auto-block touched by any swap);
> on-prem + synthetic (the end-state is fully on-prem in-India); validate-against-
> blueprint (Part 26.4 is the controlling reference).
