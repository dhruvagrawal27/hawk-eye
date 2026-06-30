# Board-Approved Artificial Intelligence Policy — Hawk-Eye

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 27.1 (RBI FREE-AI — 7 Sutras, 6 pillars, board-approved AI
> policy), Part 27.2 (MRM / SR 11-7 backbone), Part 29 (fairness), Part 30 (resilience),
> Part 34.4 (AI-specific outsourcing clauses).
> **Regulators in scope:** RBI FREE-AI Framework 2025, RBI IT Governance (ITGRCA) MD 2023,
> RBI Fraud Risk Management MD 2024, SR 11-7 (model risk), DPDP Act 2023 + Rules 2025.
> **MOCK status:** Board approval is a human/legal act. This document is the *artefact* of
> that act; the approval **record** is seeded in the governance DB
> (`policies` where `policy_type='ai_policy'`) and surfaced read-only in the dashboard
> governance view via `governance-api` (:8093).

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| Policy name | Board-Approved AI Policy |
| Policy type | `ai_policy` |
| Version | 1.0 |
| Status | `board_approved` |
| Approved by | **Board of Directors** |
| Approval date | **2026-02-18** |
| Board resolution | **BR-2026-014** |
| Owner | Chief Risk Officer (CRO), accountable to the Board |
| Review cadence | Annual, and after any material AI incident, regulatory change, or model-tier escalation |
| Next review due | 2027-02-18 |
| Evidence record | `policies` (`resolution_id='BR-2026-014'`) → rendered to `governance/docs/out/ai-policy.md` |

**Signatory body:** Board of Directors of the Bank, on the recommendation of the
AI / Model Risk Committee (chair: Dr. R. Iyer, Risk) and the Information Security
Committee (ISC). Minuted in board resolution **BR-2026-014** dated 2026-02-18.

---

## 1. Purpose and scope

### 1.1 Purpose
This Policy establishes how the Bank governs the design, approval, deployment, monitoring
and retirement of Artificial Intelligence and Machine-Learning systems, with specific
application to **Hawk-Eye**, the Bank's real-time insider and privileged-user
fraud-detection platform. It operationalises RBI's **FREE-AI Framework (2025)** and aligns
to global model-risk practice (**SR 11-7**), so that the platform can pass an RBI inspection
and run sustainably for years.

### 1.2 The defining constraint — ALERT-ONLY
Hawk-Eye **scores and explains; it never auto-blocks money or auto-classifies a person as a
fraudster.** Every consequential outcome is decided by a human, preceded by a
natural-justice hearing (the HITL gate). This is a non-negotiable design invariant of the
platform and the first principle of this Policy. No AI component in Hawk-Eye is permitted to
take an irreversible action against an employee or a transaction autonomously.

### 1.3 Scope of systems governed
This Policy covers every AI/ML model and AI-assisted component in the platform:

| Layer | Component | In scope |
|---|---|---|
| L1 | Rules / business-rules engine (deterministic) | Yes — governed as a model-equivalent (a rule change can blind detection) |
| L2 | Unsupervised anomaly detection (Isolation Forest + ECOD/COPOD) | Yes |
| L3 | Supervised tabular scorer (GBDT) | Yes |
| L4 | Sequence model | Yes |
| L5 | Graph model (XGB-Graph) | Yes |
| L6 | Risk-fusion model (`fusion-2026.2.0`) | Yes — **Tier-1** |
| LLM | TEE-attested narrative gateway (NEAR AI / Groq, `gpt-oss-120b`) | Yes — validated for grounding/hallucination, not just accuracy |

### 1.4 Out of scope
General office productivity AI not connected to the fraud-decisioning pipeline; these are
governed by the Bank's general IT acceptable-use policy.

---

## 2. The 7 Sutras (FREE-AI principles) and how Hawk-Eye honours each

The system must **demonstrably** honour all seven Sutras. Each maps to a concrete,
already-built control in the blueprint.

| # | Sutra | How Hawk-Eye demonstrates it (control) |
|---|---|---|
| 1 | **Trust** | On-prem, synthetic-data-only build; immutable WORM audit log; signed model artefacts verified on load (Part 23); TEE attestation as the trust anchor for any LLM egress (Part 25). |
| 2 | **People First** | ALERT-ONLY; natural-justice HITL gate before any classification; staff transparency notice; proportionality and works-council/union engagement (Part 29.2). |
| 3 | **Innovation** | Hybrid rules+ML layered architecture; EDD feedback loop; AWS Lightsail pilot with a clean migration to on-prem (ADR-0001 / Part 26.4) — innovate without lock-in. |
| 4 | **Fairness** | Disparate-impact testing by grade/age/gender/region/department/tenure; protected attributes never used as features; proxy monitoring; peer-group-relative scoring (Part 29.1). |
| 5 | **Accountability** | Immutable audit + human-in-the-loop; SoD personas (builder / labeler / actor / administrator); the "watch the watchers" principle — investigators are themselves audited (Part 19.6). |
| 6 | **Explainability** | Every alert carries reason codes + a grounded narrative (Parts 20.6, 25); explainability treated as a contestability right, not a feature. |
| 7 | **Resilience** | Graceful-degradation switch to rules-only fallback when ML serving is down (Part 18 / Part 30); multi-AZ/multi-DC HA; tested DR + BCP (resolution BRC-2026-008). |

---

## 3. The 6 FREE-AI pillars — the Bank's AI control surface

| Pillar | What the Bank maintains for Hawk-Eye |
|---|---|
| **Infrastructure** | On-prem-capable, all-open-source stack; AWS Lightsail pilot (`ap-south-1`, residency in-India); confidential-compute (Intel TDX + NVIDIA) for any LLM inference; Terraform parameterised `target = aws \| onprem \| lightsail`. |
| **Policy** | This Board-approved AI Policy; the MRM framework; data-protection, lawful-basis, breach-notification and transparency policies (PLATFORM-36 set). |
| **Capacity** | Annual capacity assessment reviewed by the IT Strategy Committee (ITGRCA); investigator staffing sized to alert volume; staff training on AI output and its limits. |
| **Governance** | AI / Model Risk Committee, AI Ethics Committee, ISC, ITSC and the Board/Audit chain; documented lifecycle approvals; the seeded governance inventory. |
| **Protection** | PII tokenization before egress; field-level encryption; PAM for the Bank's own admins; SBOM (CERT-In v2.0, SPDX + CycloneDX) at `ci/security/sbom/`; VAPT + ATLAS adversarial-ML red-teaming. |
| **Assurance** | Independent model validation (effective challenge); fairness audits; VAPT/red-team; internal-audit IS audit (3rd line); AI incident reporting wired to CERT-In/RBI/DPB. |

---

## 4. Roles, responsibilities and separation of duties

### 4.1 Governance bodies
- **Board of Directors** — owns this Policy; receives AI-risk and incident reporting.
- **AI / Model Risk Committee (AMRC)** — approves models and material changes, reviews
  incidents, reports to the Board; members span risk, compliance, business, tech
  (seeded: Dr. R. Iyer (chair, risk), S. Banerjee (compliance), A. Khan (business), P. Rao (tech)).
- **AI Ethics Committee** — reviews fairness results and high-impact decisions; chaired by an
  independent member (Justice (Retd.) M. Nair), with HR and Legal.
- **Information Security Committee (ISC)** — RBI-mandated, chaired from Risk.
- **IT Strategy Committee (ITSC)** — board-level; reviews the annual capacity assessment.

### 4.2 Separation of duties (SoD personas) — Part 19.6
The anti-fraud system must never be quietly turned against the Bank or an individual.
The following personas are **distinct people with distinct access**:

| Persona | May do | May **not** do |
|---|---|---|
| **Builder** (Model Engineer) | Build / deploy models | Label data; close their own alerts |
| **Labeler** | Provide EDD labels / dispositions | Deploy models; tune the rules that generate their alerts unchecked |
| **Actor** (Investigator / Fraud Ops) | Triage and act on alerts | Tune the rules that generate those alerts; deploy models |
| **Administrator** | Operate the platform / access control | Build models, label data, or close alerts |

> **Key SoD rule (Part 19.6):** the person who deploys models cannot label data or close their
> own alerts; the person who investigates cannot tune the rules that generate their alerts
> unchecked.

---

## 5. AI risk tiering

Models are tiered by **impact**, per the MRM framework (Part 27.2). Higher tiers receive
deeper validation and more frequent review.

| Tier | Definition | Hawk-Eye examples | Validation depth | Review cadence |
|---|---|---|---|---|
| **Tier-1** | Materially influences a consequential human/transaction outcome | L6 risk-fusion (`fusion-2026.2.0`) | Full independent validation + outcome analysis + fairness audit | Quarterly + on change |
| **Tier-2** | Feeds Tier-1; meaningful alerting influence | L3 supervised, L5 graph | Independent validation; fairness + drift monitoring | Semi-annual |
| **Tier-3** | Supporting / cold-start signal | L2 unsupervised | Conceptual-soundness + stability review | Annual |
| **Tier-4** | Narrative / explanatory only (no scoring) | LLM gateway | Grounding/hallucination validation; no autonomous action | Annual + on model-version change |

> Tiering note: the LLM narrative gateway is non-scoring and cannot act, but it still
> requires grounding/hallucination validation because its output is read by human deciders.

---

## 6. AI lifecycle governance (approval → testing → deployment → monitoring → retirement)

Every model traverses this gated lifecycle. Each gate produces an auditable record.

### 6.1 Approval
- Model registered in the **model inventory** (Part 27.2): owner, purpose, risk tier, data,
  version, validation status.
- A full **model card** is authored (intended use, training-data hash, features, metrics,
  limitations, known failure modes, fairness results) — this is also the natural-justice
  evidence base.
- **AMRC approval** of intent and tier.

### 6.2 Testing & independent validation
- A function **separate from the developers** performs **effective challenge** —
  conceptual soundness, data, performance, stability, outcomes (and grounding for the LLM).
- CI gates: behavioral / metamorphic / directional / regression / **fairness** tests
  (Parts 29, 31) plus security (SAST/DAST, CVE, VAPT, ATLAS red-team).
- Seeded evidence: independent validation of `fusion-2026.2.0` signed off 2026-04-30
  (`MV-2026-007`); fairness audit accepted by the Ethics Committee 2026-04-21 (`ETH-2026-006`).

### 6.3 Deployment
- Promotion approved by **AMRC** (seeded: `AMRC-2026-012`, 2026-05-02) and routed through
  **change management / CAB** (seeded: **CAB-2026-033**, 2026-05-06) — scheduled window,
  documented rollback.
- Shadow → champion/challenger → canary; **signature verified on load**.

### 6.4 Monitoring
- Ongoing drift, performance decay, stability (PSI), and **outcome analysis against realized
  fraud**; continuous fairness monitoring (bias can drift, including via the EDD feedback loop).
- **AI incident reporting** uses FREE-AI's indicative incident form; incidents are logged
  (`incidents` table) and reported per the breach-notification workflow (CERT-In 6h / RBI / DPB
  as applicable).

### 6.5 Retirement
- Model retirement is **governed** — documented decision, removal from serving, retention of
  the model card and validation history for audit, and superseding-model linkage.

---

## 7. AI-specific outsourcing obligation

Per FREE-AI and Part 34.4, **AI-specific clauses** must appear in every outsourcing agreement
touching the AI pipeline (AWS, NEAR AI, Groq), covering algorithmic bias, third-party /
subcontractor AI use, data confidentiality / localization, audit rights, and a
**no-training-on-our-data** commitment. The clause template is at
`governance/vendor-risk/ai-clause-template.md`; per-vendor due diligence is at
`governance/vendor-risk/{aws,near-ai,groq}.md`; the consolidated register is at
`governance/vendor-risk/outsourcing-register.md`.

---

## 8. Cross-references

- Model-risk inventory & validation: `governance/validation/`, Part 27.2.
- Fairness / ethics: `governance/docs/transparency-notice.md`, Part 29.
- Data protection: `governance/docs/dpia.md`, `governance/docs/lawful-basis-map.md`,
  `governance/docs/breach-notification.md`, `governance/docs/dpo-appointment.md`, Part 28.
- Resilience / BCP: `governance/bcp.md` (BRC-2026-008), Part 30.
- Vendor / outsourcing risk: `governance/vendor-risk/`, Part 34.4.
- Deployment deviation: `docs/adr/ADR-0001-ec2-in-vpc.md` (AWS Lightsail; on-prem is production).
