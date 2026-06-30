# Vendor Due Diligence — Groq (Secondary LLM Path, Non-TEE)

> **Workstream:** PLATFORM-38 (vendor / outsourcing risk).
> **Blueprint basis:** Part 34.4 (vendor due diligence; AI-specific clauses; exit strategy;
> concentration risk; SBOM), Part 25.4 (failover chain; Groq is **not** a TEE path —
> `tee_attested=false` logged; PII still tokenized), Part 25.3 (tokenize before egress),
> Part 26.4 (on-prem migration).
> **Regulators in scope:** RBI Outsourcing of IT Services Directions 2023, RBI FREE-AI 2025,
> DPDP Act 2023, RBI ITGRCA MD 2023, CERT-In v2.0 (SBOM).
> **MOCK status:** the assessment is a human act; the **record** is seeded in the governance DB
> (`vendors` where `name='Groq'`).

---

## Vendor record (seeded governance record)

| Field | Value |
|---|---|
| Vendor | **Groq** |
| Vendor type | `llm_gateway` (secondary / tertiary, **non-TEE**) |
| Endpoint / model | `api.groq.com/openai/v1`, `openai/gpt-oss-120b` |
| Status | `assessed` |
| Due diligence | **Non-TEE path**; `tee_attested=false` logged; **PII tokenized** before egress |
| SLA | Fast OpenAI-compatible; **secondary only** |
| Exit strategy | Drop to template fallback or on-prem node |
| Concentration risk | Tertiary; **not on the critical path** |
| AI clauses | Data confidentiality; **no-training** clause |
| SBOM linkage | `ci/security/sbom/` (SPDX + CycloneDX) |
| Evidence record | `vendors` (`name='Groq'`) |

---

## 1. Role in the failover chain (Part 25.4)

```
1. NEAR AI  (TEE-attested, primary)        →  tee_attested=true
2. Groq     (non-TEE, secondary)           →  tee_attested=false  (deliberate, LOGGED degradation; PII still tokenized)
3. Template (deterministic, tertiary)      →  UI never breaks
```

Groq is the **fast, OpenAI-compatible secondary** used only when NEAR AI errors/times out. The
absence of a TEE is **explicitly recorded** in the per-narrative audit memo
(`tee_attested=false`, `attestation_id=null`) — a deliberate, auditable degradation, not a gap.
PII is **still tokenized before egress**, so even on the non-TEE path no raw PII leaves the
perimeter.

---

## 2. Material-outsourcing classification

| Question | Answer |
|---|---|
| Material outsourcing under RBI 2023? | Yes, but **tertiary** — narrative-only, off the scoring/decision path. |
| TEE protection? | **No** — non-TEE path; this is the key residual-risk note for this vendor. |
| Data exposure | Tokenized features only; no raw PII; no scoring or action by the LLM (ALERT-ONLY). |

---

## 3. Due-diligence questionnaire (responses)

| # | Area | Question | Response |
|---|---|---|---|
| Q1 | Confidential compute | TEE / attestation? | **No TEE** — `tee_attested=false` recorded every time Groq is used. |
| Q2 | PII exposure | Does the provider see PII? | No raw PII — tokenized before egress (Part 25.3); but no TEE, so tokenization is the sole barrier. |
| Q3 | Training on our data | Train on our prompts? | **No** — `no-training` clause applied. |
| Q4 | Data confidentiality | Confidentiality commitment? | Data-confidentiality clause applied. |
| Q5 | Criticality | On the critical path? | **No** — secondary/tertiary; template fallback guarantees the UI. |
| Q6 | Auditability | Provenance recorded? | Audit memo logs provider=`groq`, `tee_attested=false`, model, `prompt_hash`, timestamp. |
| Q7 | Algorithmic bias | Bias in narratives? | Narrative non-scoring; low temperature; Tier-4 grounding validation. |
| Q8 | SBOM | Software bill of materials? | Our SBOM at `ci/security/sbom/` (SPDX + CycloneDX). |

---

## 4. SLA terms

| Metric | Commitment |
|---|---|
| Latency | Fast (OpenAI-compatible inference) |
| Role | Secondary only — invoked on NEAR AI failure |
| Continuity | Falls through to deterministic template if Groq also fails |
| Data handling | Tokenized input; no training; confidentiality clause |

---

## 5. Exit strategy
Drop to the **deterministic template fallback** (immediate, no dependency) or to the **on-prem
node** (Part 26.4). Because Groq is non-critical and off the decision path, exit has **no
detection impact** — at worst the narrative becomes a template.

---

## 6. Concentration-risk assessment (RBI Outsourcing 2023)

| Dimension | Assessment |
|---|---|
| Dependence | **None material** — tertiary, not on the critical path. |
| Residual risk | **Low** — its only residual is the non-TEE path, mitigated by tokenization + audit logging + its non-critical role. |

---

## 7. AI-specific clauses (FREE-AI)
**Data confidentiality** and **no-training-on-our-data** clauses apply (from
`ai-clause-template.md`). Because Groq is non-TEE and tertiary, the assessment emphasises the
tokenization + audit-logging compensating controls.

---

## 8. SBOM linkage
SBOM at `ci/security/sbom/` (SPDX + CycloneDX), `ci/security/sbom.sh`; CVE scans `ci/security/scan.sh`.

---

## 9. Cross-references
- Consolidated register: `governance/vendor-risk/outsourcing-register.md`.
- AI-clause template: `governance/vendor-risk/ai-clause-template.md`.
- NEAR AI (primary, TEE): `governance/vendor-risk/near-ai.md`.
- Cross-border transfer analysis: `governance/docs/dpia.md` §4 (DPO-2026-004).
- AI Policy: `governance/docs/ai-policy.md` (BR-2026-014).
