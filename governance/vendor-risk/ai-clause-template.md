# AI-Specific Outsourcing Clause Template (FREE-AI)

> **Workstream:** PLATFORM-38 (vendor / outsourcing risk).
> **Blueprint basis:** Part 27.1 + Part 34.4 — **AI-specific clauses in outsourcing agreements**
> covering **algorithmic bias, third-party/subcontractor AI use, and data confidentiality**
> (FREE-AI), directly relevant to the AWS + NEAR AI / Groq vendors; Part 25.3 (PII tokenized
> before egress); Part 28.1 (data localization / cross-border transfer); Part 19.6 (governance).
> **Regulators in scope:** RBI FREE-AI 2025, RBI Outsourcing of IT Services Directions 2023,
> DPDP Act 2023, RBI ITGRCA MD 2023, CERT-In v2.0.

This template provides the **standard AI-specific clauses** to be incorporated into every
outsourcing agreement that touches the AI pipeline. Applicability per vendor is summarised in
`outsourcing-register.md`; per-vendor application is recorded in `aws.md`, `near-ai.md`,
`groq.md`.

---

## Clause 1 — Algorithmic bias & fairness
The Service Provider shall not introduce, and shall take reasonable measures to avoid,
**algorithmic bias** in any AI/ML processing performed on the Bank's behalf. Where the Provider's
service generates analytical or narrative output consumed by the Bank's human deciders, that
output shall be **non-discriminatory** and shall not rely on protected attributes. The Bank
retains the right to conduct **fairness/disparate-impact testing** and to require remediation of
any bias identified. *(FREE-AI Fairness Sutra; Part 29.)*

## Clause 2 — Third-party / subcontractor AI use
The Service Provider shall **disclose** any third party or subcontractor that performs AI/ML
processing on the Bank's data, and shall **flow down** the obligations of this template to such
subcontractors. No new AI subcontractor shall be engaged for the Bank's data without **prior
written notice** to the Bank. *(FREE-AI; RBI Outsourcing 2023 sub-contracting controls.)*

## Clause 3 — Data confidentiality & no-training-on-our-data
The Service Provider shall keep the Bank's data **strictly confidential** and shall **not use the
Bank's prompts, inputs, or outputs to train, fine-tune, or improve any model**, nor retain them
beyond what is necessary to render the service. *(FREE-AI data-confidentiality; the
"no-training-on-our-data" commitment.)*

## Clause 4 — Data localization & cross-border transfer
Personal data shall be processed in accordance with the **DPDP Act 2023** and shall not be
transferred to a restricted jurisdiction. Where processing occurs outside India, the Provider
shall support the Bank's controls: **PII is tokenized before egress** (Part 25.3) and, where
applicable, processed within a **TEE with verifiable attestation**. The Bank's residency intent
is **in-India** (region of record `ap-south-1`), with an **on-prem migration** end-state
(Part 26.4). *(DPDP; Part 28.1.)*

## Clause 5 — Confidential compute & attestation (where offered)
Where the service offers confidential compute, the Provider shall provide **per-request
cryptographic attestation** (e.g., Intel TDX + NVIDIA) that the Bank may **verify and store** for
audit. Where no TEE is available (e.g., a secondary/tertiary path), the absence shall be
**recorded** by the Bank (`tee_attested=false`) and compensating controls (tokenization) shall
apply. *(Part 25.)*

## Clause 6 — Audit rights & assurance
The Bank (and its regulators, including the RBI) shall have the **right to audit** the Provider's
controls relevant to this service, or to rely on the Provider's independent assurance
(ISO 27001 / SOC 2), with a right to information and remediation. *(RBI Outsourcing 2023 audit
rights; ITGRCA.)*

## Clause 7 — AI incident notification
The Provider shall **notify the Bank** of any incident affecting the AI service or the Bank's
data without undue delay, in time to support the Bank's **CERT-In 6-hour** reporting and its
**DPB / RBI** obligations, and shall cooperate with the Bank's incident response. *(Part 28.1;
breach-notification workflow.)*

## Clause 8 — Explainability & provenance
Where the service produces output read by the Bank's deciders, the Provider shall not obstruct
the Bank's ability to record **provenance** (provider, model, `tee_attested`, `attestation_id`,
`prompt_hash`, timestamp) so that every AI-written word is auditable. *(FREE-AI Explainability;
Part 25.4.)*

## Clause 9 — Exit, data return & deletion
On termination the Provider shall **return and/or certifiably delete** the Bank's data and shall
support a clean exit. The Bank's architecture is designed so that the service can be **swapped to
an on-prem equivalent** without application rewrite (Part 26.4). *(RBI Outsourcing 2023 exit
strategy.)*

## Clause 10 — No autonomous action (ALERT-ONLY)
The Provider's AI service shall **not** be used to take any **autonomous consequential action**
against a person or a transaction. The Provider acknowledges the service is **explanatory/advisory
only**; all decisions are made by the Bank's humans through the natural-justice HITL gate.
*(Golden rule #1; Part 29.2.)*

---

## Applicability matrix

| Clause | AWS (infra) | NEAR AI (TEE LLM) | Groq (non-TEE LLM) |
|---|---|---|---|
| 1 Algorithmic bias | N/A (infra) | Yes | Yes |
| 2 Subcontractor AI | Disclosure | Yes | Yes |
| 3 Confidentiality / no-training | Yes (data) | Yes | Yes |
| 4 Localization / transfer | Yes | Yes | Yes |
| 5 Confidential compute / attestation | N/A | Yes (TEE) | Recorded as `tee_attested=false` |
| 6 Audit rights | Yes | Yes | Yes |
| 7 Incident notification | Yes | Yes | Yes |
| 8 Explainability / provenance | N/A | Yes | Yes |
| 9 Exit / return / deletion | Yes | Yes | Yes |
| 10 No autonomous action | N/A | Yes | Yes |

---

## Cross-references
- Consolidated register: `governance/vendor-risk/outsourcing-register.md`.
- Per-vendor application: `governance/vendor-risk/aws.md`, `near-ai.md`, `groq.md`.
- AI Policy (outsourcing obligation): `governance/docs/ai-policy.md` §7 (BR-2026-014).
- Cross-border transfer: `governance/docs/dpia.md` §4; `governance/docs/lawful-basis-map.md`.
