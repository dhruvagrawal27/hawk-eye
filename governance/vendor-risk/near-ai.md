# Vendor Due Diligence — NEAR AI (TEE-Attested LLM Gateway)

> **Workstream:** PLATFORM-38 (vendor / outsourcing risk).
> **Blueprint basis:** Part 34.4 (vendor due diligence; AI-specific outsourcing clauses —
> algorithmic bias, subcontractor AI use, data confidentiality; exit strategy; concentration
> risk; SBOM), Part 25 (TEE-attested narrative LLM gateway), Part 25.3 (PII tokenized before
> egress), Part 28.1 (cross-border transfer), Part 26.4 (on-prem migration).
> **Regulators in scope:** RBI Outsourcing of IT Services Directions 2023, RBI FREE-AI 2025,
> DPDP Act 2023 (cross-border transfer), RBI ITGRCA MD 2023, CERT-In v2.0 (SBOM).
> **MOCK status:** the assessment is a human act; the **record** is seeded in the governance DB
> (`vendors` where `name='NEAR AI'`).

---

## Vendor record (seeded governance record)

| Field | Value |
|---|---|
| Vendor | **NEAR AI** |
| Vendor type | `llm_gateway` (primary, TEE-attested) |
| Endpoint / model | `cloud-api.near.ai/v1`, `openai/gpt-oss-120b`, gateway mode |
| Status | `assessed` |
| Due diligence | TEE attestation verified per-request; **no data retention** |
| SLA | Best-effort; **deterministic template fallback guarantees the UI** |
| Exit strategy | Swap to on-prem `gpt-oss-120b` in TDX (same OpenAI API) |
| Concentration risk | Secondary **Groq** + template fallback reduce concentration |
| AI clauses | Algorithmic bias, subcontractor-AI use, data confidentiality, **no-training-on-data** |
| SBOM linkage | `ci/security/sbom/` (SPDX + CycloneDX) |
| Evidence record | `vendors` (`name='NEAR AI'`) |

---

## 1. Material-outsourcing classification

| Question | Answer |
|---|---|
| Material outsourcing under RBI 2023? | **Yes** — an external AI service in the alert-narrative path. |
| Is it on the critical path? | **No** — narrative is **explanatory only**; the UI never breaks because of a deterministic template fallback (Part 25.4). The LLM **never scores or acts** (ALERT-ONLY). |
| Data exposure | **Tokenized features only** — PII is hashed/tokenized **before** egress (Part 25.3); the TEE means even that is invisible to the provider. |

---

## 2. Why an external LLM is defensible here (the TEE trust anchor)

- **Intel TDX (CPU) + NVIDIA H200 (GPU) confidential compute** — data is **encrypted in use**
  (memory, VRAM, PCIe); even the infrastructure operator cannot read it.
- **TLS terminates inside the enclave** (gateway mode) — prompts are never plaintext outside hardware.
- **Per-request cryptographic attestation** — each TEE emits a signed quote (Intel TDX + NVIDIA
  dual attestation); the gateway **verifies and stores** the attestation report for audit
  (`attestation_id` in the audit memo).
- **Defense in depth** — PII is tokenized before egress regardless, so the LLM sees behaviour +
  structure + tokens, never raw PII.

---

## 3. Due-diligence questionnaire (responses)

| # | Area | Question | Response |
|---|---|---|---|
| Q1 | Confidential compute | TEE / attestation? | Intel TDX + NVIDIA dual attestation; per-request quote verified and stored. |
| Q2 | Data retention | Retain prompts/outputs? | **No data retention**; verified per-request via attestation gateway mode. |
| Q3 | Training on our data | Train on our prompts? | **No** — `no-training-on-our-data` clause applied (FREE-AI). |
| Q4 | PII exposure | Does the provider see PII? | No — PII tokenized before egress; TEE prevents provider access even to tokens. |
| Q5 | Cross-border | Where does inference run? | Documented in DPIA §4; not a restricted jurisdiction; on-prem migration preferred end-state for full residency. |
| Q6 | Algorithmic bias | Bias in generated narratives? | AI-bias clause applied; narrative is non-scoring; low temperature (0.2); Tier-4 grounding/hallucination validation. |
| Q7 | Subcontractor AI | Third-party / subcontractor AI use? | Subcontractor-AI clause applied; disclosure required. |
| Q8 | Availability | Outage handling? | Failover to Groq, then **deterministic template** — UI never breaks (Part 25.4). |
| Q9 | Auditability | Provenance of AI output? | Every narrative writes an audit memo: provider, `tee_attested`, `attestation_id`, model, `prompt_hash`, timestamp. |
| Q10 | SBOM | Software bill of materials? | Our SBOM at `ci/security/sbom/` (SPDX + CycloneDX). |

---

## 4. SLA terms

| Metric | Commitment |
|---|---|
| Availability | Best-effort (external) |
| Continuity guarantee | **Deterministic template fallback** — the dashboard always renders a narrative |
| Attestation | Per-request TEE quote verified + stored |
| Data handling | No retention; tokenized input; no training on our data |

---

## 5. Exit strategy

Swap to an **on-prem confidential-compute node** — the Bank's own **H100/H200 in Intel TDX**
running **`gpt-oss-120b` locally**, with the **same OpenAI-compatible interface** and the **same
attestation guarantees** (Part 26.4). Because the client is the standard OpenAI SDK pointed at a
`base_url`, exit is a configuration change plus standing up the on-prem node — no application
rewrite. This also achieves **full data residency**.

---

## 6. Concentration-risk assessment (RBI Outsourcing 2023)

| Dimension | Assessment |
|---|---|
| Single-provider dependence | Mitigated by a **secondary (Groq)** and a **template fallback**; NEAR AI is not a single point of failure. |
| Criticality | Narrative is explanatory-only and off the scoring/decision path, so provider loss degrades UX, not detection. |
| Residual concentration risk | **Low** — multi-provider + template + on-prem migration path. |

---

## 7. AI-specific clauses (FREE-AI)
All clauses from `ai-clause-template.md` apply: **algorithmic bias**, **third-party/subcontractor
AI use**, **data confidentiality & localization**, **audit rights**, and
**no-training-on-our-data**.

---

## 8. SBOM linkage
SBOM at `ci/security/sbom/` (SPDX `sbom.spdx.json` + CycloneDX `sbom.cdx.json`), generated by
`ci/security/sbom.sh`; CVE scans via `ci/security/scan.sh`.

---

## 9. Cross-references
- Consolidated register: `governance/vendor-risk/outsourcing-register.md`.
- AI-clause template: `governance/vendor-risk/ai-clause-template.md`.
- Cross-border transfer analysis: `governance/docs/dpia.md` §4 (DPO-2026-004).
- Groq (secondary): `governance/vendor-risk/groq.md`.
- AI Policy: `governance/docs/ai-policy.md` (BR-2026-014).
