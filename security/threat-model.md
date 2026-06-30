# Hawk-Eye Threat Model — STRIDE + Insider Lens + ML-Specific (PLATFORM-20)

> **Purpose.** Model Hawk-Eye as the single most attractive internal target in the bank — it holds
> the unified behavioural record of every employee and privileged user — and enumerate the threats
> against it using **STRIDE**, the **three attacker classes**, the **insider lens**, and the
> **ML-specific** (MITRE ATLAS) attack surface. Define the **data-flow + trust boundaries**, and tie
> every threat to a concrete mitigation that already exists in the blueprint and in this repo's
> security controls.
>
> **Blueprint:** Part 19.1 (STRIDE + insider lens + ML-specific), Part 19.3 (platform &
> infrastructure security), Part 15 (adversarial insiders / low-and-slow), Part 27 (model risk),
> Part 25 (TEE-attested LLM gateway). **Task:** PLATFORM-20. **Status:** DOCUMENTATION (regulator-grade).
>
> **Companion:** `security/framework-mapping.md` (ML-attack→ATLAS table + framework alignment +
> FREE-AI 7-Sutra→control map). **Cross-references:** `security/zero-trust-policy.md` (zones,
> egress allow-list, mTLS), `security/admin-access-policy.md` (PAM / watch-the-watchers),
> `security/vuln-mgmt/` (patch SLAs), `security/reports/` (VAPT / red-team / model-risk evidence).

---

## 0. Golden-rule alignment

- **ALERT-ONLY.** This threat model defends a system that *scores and explains*; it never auto-blocks
  money or auto-classifies fraud. A compromise of Hawk-Eye therefore cannot, by design, move funds —
  it can at worst *blind*, *poison*, or *defame*. Those are the harms this model defends against, and
  the natural-justice human-in-the-loop (HITL) gate (`hitl-gate`, :8094) is itself a control that
  caps the blast radius of a corrupted score.
- **ON-PREM + SYNTHETIC + NO INTERNET EGRESS.** The running system holds **synthetic data only** and
  has **no general internet egress** (the only outbound path is the FQDN-pinned NEAR AI + Groq LLM
  allow-list, TEE-attested, from the governance/compute zones — see `security/zero-trust-policy.md`
  §4). No real PII or credentials are at risk in the pilot; production (on-prem, in-India) inherits
  the same posture with real data behind the air-gap.
- **WATCH-THE-WATCHERS (quis custodiet).** The irony stated to leadership: *a system that watches
  privileged users is itself operated by privileged users, and must hold itself to a stricter
  standard than anything it monitors.* Every investigator and admin action is written to the
  append-only WORM audit log; the people with the most power are the most observed.
- **VALIDATE-AGAINST-BLUEPRINT.** Threats and mitigations trace to Part 19.1–19.6; the canonical
  deviation (deploy target = **AWS Lightsail** for the pilot, ADR-0001) does not change the trust
  boundaries — Lightsail is single-tenant, synthetic, alert-only; production remains on-prem in-India.

---

## 1. Why this system is the crown jewel (assets at risk)

Hawk-Eye is, by design, the one system a sophisticated insider most wants to **blind, poison, or
evade**. A fraud-detection platform that is itself insecure does not merely fail — it becomes a new
toxic-combination and a single point of catastrophic compromise. The assets, ranked by sensitivity:

| # | Asset | Where it lives (zone / service) | Why an attacker wants it |
|---|---|---|---|
| A1 | **Unified behavioural record** (every employee + privileged user, L0 event model) | data zone — ClickHouse (8123/9000), Kafka (9092) | The bank's most concentrated surveillance dataset; recovering it enables targeted evasion or extortion |
| A2 | **PII / PAN it must read** (re-identification vault, token↔real map) | data zone — vault / MinIO; never egresses | Direct privacy harm; DPDP-regulated (up to ₹250 cr) |
| A3 | **Model artifacts** (L2–L6, the L6 fusion model `fusion-2026.2.0`) | compute/serving — MLflow (5000), model registry / MinIO | IP theft + enables *offline* crafting of evasive activity |
| A4 | **Training data + EDD feedback labels** | data zone — ClickHouse, object store | Poisoning here teaches the model that fraud is "normal" |
| A5 | **Detection logic, thresholds, rules** (L1 BRE, fusion weights) | app/governance — `backend`, BRE config, governance-api (8093) | Knowing thresholds lets an insider stay "just under" detection |
| A6 | **Scores, reason codes, narratives, alerts** (L6 + LLM gateway output) | app — `backend`, dashboard (5173) | Reveals who is being watched and why; manipulation defames or exonerates |
| A7 | **The immutable audit log** (who viewed whom, who closed which alert) | data/governance — WORM store | Tampering here erases the "watch-the-watchers" guarantee |
| A8 | **Admin / service credentials, LLM keys, PII-HMAC key** | governance — Vault (8200) | Standing keys = standing power over everything above |

---

## 2. The three attacker classes (Part 19.1)

The threat model is organised around **three** distinct adversaries. Every STRIDE entry in §4 and
every ML attack in §5 is attributed to one or more of these.

### 2.1 Class A — External attacker (breaches the perimeter)
An outsider who gains a foothold (phishing, exposed service, supply-chain implant) and pivots toward
the crown jewels. **Primary defence:** the zero-trust posture — default-deny east-west, mTLS +
SPIFFE per-hop authn, the data zone unreachable from the edge, no internet egress, and PAM-gated
management (`security/zero-trust-policy.md` §1–§5). An external attacker who lands in the edge zone
finds it *cannot* reach `postgres`/`clickhouse`/`minio`/`kafka` at all (explicit DENY).

### 2.2 Class B — Malicious insider (has some platform access)
The hardest class: a privileged user *inside the programme* — a builder, labeler, actor (investigator),
or administrator — who abuses legitimate access to data, labels, models, or thresholds. **Primary
defence:** **Separation of Duties (SoD)** across the four personas (the person who deploys models
cannot label data or close their own alerts), PAM with session recording for all admin access
(`security/admin-access-policy.md`), least-privilege named service accounts (no shared/anonymous —
the exact anti-pattern this platform exists to catch), and the WORM audit log over *every* insider
action including investigators' own views and dispositions.

### 2.3 Class C — The monitored subjects evading detection
Employees / privileged users who are **not** attacking the platform's confidentiality but are
**gaming the model** — shaping their own activity to stay below thresholds, poisoning their
behavioural baseline "low-and-slow," or gaming the EDD feedback labels so the model learns their
fraud is normal. This is the class the *detection design itself* must resist. **Primary defence:**
**peer-relative (not absolute) baselines**, undisclosed thresholds/logic, randomized review
sampling, change-point + peer-anchored baselines that resist gradual drift, an **ensemble of diverse
detectors** (rules + unsupervised + supervised + graph) so evading one does not evade all, and
recurring adversarial-ML evaluation (`security/reports/redteam.md`).

> **The insider lens (overarching).** Classes B and C are what make this system unlike a normal app.
> The defender must assume the adversary **knows the system exists, knows roughly how it works, and
> has time.** Hence: never expose logic or thresholds; never rely on a single detector or a single
> post-hoc explanation; segregate duties so no one person can quietly turn the system against the
> bank or an individual; and watch the watchers without exception.

---

## 3. Data-flow & trust boundaries

### 3.1 The detection data flow (L0 → L7)

```
                            ┌──────────────────────── TRUST BOUNDARY: INTERNET / EDGE ───────────────────────┐
  Investigator/API ──443──▶ │ ALB + WAF (edge zone)  — TLS terminates here; NO app pods; cannot reach data   │
                            └───────────────┬───────────────────────────────────────────────────────────────┘
                                            │ E2 (mTLS, authn)
        ┌───────────────────────────── TRUST BOUNDARY: APP ZONE ──────────────────────────────────────┐
        │  backend(8000) · frontend(5173) · keycloak(8080) · governance-api(8093) · hitl-gate(8094)    │
        └───┬─────────────────────────┬───────────────────────────┬────────────────────────┬──────────┘
            │ E3 (read)               │ E4 (infer)                │ E5 (attest/PAM/vault)   │ HITL decision
   ┌────────▼─────────── DATA ZONE ───▼──────────┐   ┌────────────▼──── COMPUTE/SERVING ──┐ │
   │ Kafka(9092) → Flink(8081) → ClickHouse      │   │ serving(8001) KServe v2: L2..L6    │ │
   │ (8123/9000) · Redis(6379) · MinIO(9001)     │◀──┤ MLflow(5000) · Airflow(8088)       │ │
   │ · schema-registry(8085)                     │E6 │ model registry / artifacts         │ │
   │ ── L0 unified event model (synthetic) ──    │   └─────────┬──────────────────────────┘ │
   │ ── training data + EDD labels (A4) ──        │            │ E7 attest before any LLM    │
   │ ── re-identification vault / PII map (A2) ── │   ┌────────▼──── GOVERNANCE ZONE ──────┐ │
   │ ── WORM audit log (A7) ──                    │   │ tee-attestation(8090) · pam-shim   │ │
   └─────────────────────────────────────────────┘   │ (8091) · degradation-switch(8092)  │ │
                                                      │ · vault(8200, keys A8)             │ │
        ┌─────── MANAGEMENT ZONE (PAM-gated) ──────┐  └─────────┬──────────────────────────┘ │
        │ prometheus · grafana · alertmanager ·    │            │ E8/E9  ── ONLY egress ──     │
        │ otel-collector · ArgoCD · bastion        │   ┌────────▼─── TRUST BOUNDARY: TEE / EGRESS ──┐
        │ (scrape-out read-only + break-glass PAM) │   │ NAT FQDN allow-list 443:                   │
        └──────────────────────────────────────────┘   │  cloud-api.near.ai (TEE-attested) ·        │
                                                        │  api.groq.com (tokenized, tee=false)       │
                                                        │  PII HMAC-tokenized BEFORE egress (Part25) │
                                                        └────────────────────────────────────────────┘
```

### 3.2 Trust boundaries (where data changes hands / privilege level)

The six **zero-trust zones** (`security/zero-trust-policy.md` §2) *are* the trust boundaries. Each
boundary crossing is mTLS + per-hop authn (SPIFFE identity), default-deny, opened only on the
explicit edges E1–E11:

| TB | Boundary crossed | What changes | Controls at the boundary |
|---|---|---|---|
| **TB1** | Internet → **edge** | Untrusted → DMZ | WAF, TLS terminate, ALB-only public subnet; **edge→data DENIED** |
| **TB2** | edge → **app** | DMZ → authenticated app | mTLS, Keycloak OIDC + SoD role; no data-zone reach from edge |
| **TB3** | app → **data** | App → crown-jewel store | mTLS, least-privilege service account, field-level tokenization/masking of PII (A2) |
| **TB4** | app → **compute/serving** | App → model plane | mTLS; serving is internal-only, authenticated, rate-limited (anti-extraction) |
| **TB5** | app/compute → **governance** | → control plane (attest, PAM, keys) | mTLS; Vault secrets by reference; TEE attestation required before any LLM call |
| **TB6** | governance/compute → **NAT → TEE/LLM** | Perimeter → external LLM | **The only egress.** FQDN-pinned, PII HMAC-tokenized first, TEE attestation verified + stored |
| **TB7** | management → workloads | Ops → everything (highest privilege) | **Scrape-out read-only** + **PAM break-glass only**; session-recorded; WORM-logged |
| **TB8** | persona → persona (SoD) | builder ⟂ labeler ⟂ actor ⟂ administrator | Logical boundary enforced by RBAC + distinct accounts; no one persona spans two |

> **Note.** TB8 is not a network boundary but a **duties** boundary — the most important one against
> Class B. It is enforced by `governance/` SoD personas + RBAC, not by `NetworkPolicy`, and is the
> reason a single compromised human cannot poison-and-deploy-and-close in one motion.

---

## 4. STRIDE across the platform

STRIDE applied per component, each row attributed to attacker class (A/B/C) and tied to a concrete
control. "Mitigation" cites the blueprint Part and/or the repo control file.

### 4.1 S — Spoofing (identity)
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| Service-to-service | A pod impersonates `serving` or `backend` to read features or scores | A, B | Per-service **SPIFFE identity** + **mTLS** both ways; no shared/anonymous accounts (Part 19.3; zero-trust §5) |
| Investigator login | Stolen/guessed analyst credential to view cases | A, B | Keycloak OIDC + MFA, **named** accounts, SoD role binding; session controls (Part 19.3) |
| Admin | Someone acts as platform admin without attribution | B | **PAM-brokered, named, session-recorded** access only; no standing admin (`admin-access-policy.md`) |
| LLM gateway | A spoofed enclave returns a tampered narrative | A | **Per-request TEE attestation** (Intel TDX + NVIDIA) verified + stored before trusting output (Part 25.2) |

### 4.2 T — Tampering (integrity)
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| Training data / EDD labels (A4) | Insider corrupts data or labels to teach "fraud = normal" | B, C | **SoD** (build⟂label⟂act⟂admin), data **provenance/lineage**, anomaly-check the training set, immutable label audit, peer-anchored + change-point baselines (Part 19.2, 19.3) |
| Model artifacts (A3) | Swap/poison a model file in the registry | A, B | Artifacts **encrypted at rest + signed**; **signature verified on load**; access-controlled registry with access logging (Part 19.2, 19.4) |
| Rules / thresholds (A5) | Quietly weaken a rule or raise a threshold | B | Every rule **versioned + four-eyes change** (CAB); config/threshold changes monitored in SIEM (Part 19.5; `admin-access-policy.md`) |
| Audit log (A7) | Erase "who viewed whom / who closed what" | A, B | **Append-only / WORM**, replicated, immutable — tampering is detectable and the log is itself a crown jewel (Part 19.3) |
| Score/narrative in flight | Alter a score or reason code before display | A | mTLS integrity end-to-end; deterministic L1–L6 scoring; LLM only *explains*, never scores (Part 25.1) |

### 4.3 R — Repudiation (non-attribution)
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| Investigator action | "I never viewed that employee / never closed that alert" | B | **Every view and disposition WORM-logged** with named identity (watch-the-watchers, Part 19.3) |
| Admin action | "I didn't change that config" | B | PAM session recording + WORM audit of all privileged actions (`admin-access-policy.md`) |
| LLM-written narrative | "The AI invented that" / provenance unclear | A, B | **Audit memo per narrative**: provider, `tee_attested`, `attestation_id`, model, `prompt_hash`, ts (Part 25.4) |

### 4.4 I — Information disclosure (confidentiality)
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| PII / PAN (A2) | Investigator or attacker reads more than need-to-know | A, B | **Field-level encryption / tokenization / masking**; analysts see only assigned cases (RBAC + need-to-know); HSM/Vault keys (Part 19.3) |
| Behavioural record (A1) | Bulk exfiltration of the surveillance dataset | A, B | Data zone **most-isolated**, no egress, no edge reach; data-access monitored in SIEM (zero-trust §2; Part 19.5) |
| Model (A3) | Inversion / membership inference to recover training data | A, C | Inference API internal-only, authenticated, **rate-limited**; no raw scores externally; DP/regularization where feasible; monitor extraction-pattern querying (Part 19.2) |
| LLM egress | Prompt leaks real PII to an external provider | A | **HMAC tokenization before egress** + **TEE encrypts data in use** — provider sees tokens only, and even those are invisible (Part 25.3) |

### 4.5 D — Denial of service (availability) — *here, "blinding" the watcher*
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| Detection pipeline | Flood/kill the scoring path so fraud goes unseen | A, C | HA + DR for Kafka/ClickHouse/serving; **graceful degradation switch** → rules-only fallback (never goes dark on known typologies) (Part 19.3, 30) |
| LLM gateway | External LLM down → no narratives | A | **Primary→secondary→deterministic template** failover; UI never breaks; degradation is logged (Part 25.4) |
| Alert path | Alert fatigue weaponised (drown analysts) | C | L6 fusion = one alert per entity, ranked by exposure, alert budgeting (Part 15) |
| Audit log | DoS the immutable log to blind oversight | A, B | Audit log replicated + immutable; loss-of-audit is itself an alertable condition (Part 19.3, 19.5) |

### 4.6 E — Elevation of privilege
| Target | Threat | Class | Mitigation |
|---|---|---|---|
| Service account | A workload escalates to read the whole subnet / registry | A, B | **Least-privilege** scoped accounts; micro-segmentation; a service reaches only its named peers (zero-trust §3) |
| Persona boundary (TB8) | A labeler grants themselves builder/actor rights (self-grant) | B | **SoD enforced by RBAC**; entitlement self-grant is *itself a modeled red flag* the platform detects (Part 19.2, 19.3) |
| Management zone | Lateral move from a scraped exporter into the model plane | A | Management reaches workloads **only** via read-only scrape + PAM; cannot initiate to data/compute otherwise (zero-trust §3, E10/E11) |
| Vault / keys (A8) | Steal LLM keys / PII-HMAC key for standing power | A, B | Secrets **by reference** from Vault/SSM, short-lived SPIRE SVIDs, no long-lived keys, HSM-backed (zero-trust §5; Part 19.3) |

---

## 5. ML-specific attack surface (insider + subject lens)

STRIDE covers the *system*; the *models* have their own attack surface (MITRE ATLAS). The full
attack→ATLAS→mitigation table lives in **`security/framework-mapping.md` §1**. Summarised by attacker
class here so the threat model is self-contained:

| ML attack | Mainly which class | One-line threat | Anchor mitigation |
|---|---|---|---|
| **Evasion / adversarial perturbation** | C (subjects) | Insider crafts activity to stay just under detection ("insiders know the thresholds") | Peer-relative baselines; hidden logic; randomized sampling; **diverse ensemble** so evading one ≠ evading all |
| **Data / label poisoning** | B (insider) | Privileged user corrupts training data or "low-and-slow" poisons their baseline / games EDD labels | SoD on data vs labels vs models; lineage; anomaly-check training set; change-point baselines; immutable label audit |
| **Model inversion / membership inference** | A, C | Query the model to recover sensitive employee/customer data | Internal-only rate-limited API; no raw external scores; DP/regularization; extraction-pattern monitoring |
| **Model extraction / theft** | A, B | Steal the model → IP loss + offline evasion crafting | Encrypted + signed artifacts; no model leaves the perimeter; registry access logging |
| **Explanation manipulation** | B, C | Adversarial scaffolding fools LIME/SHAP into innocuous explanations | Don't rely solely on post-hoc XAI; rule provenance; cross-check vs rules + raw evidence; causal/invariant methods |
| **ML supply-chain compromise (AML.T0048)** | A | Malicious code/data in a dep, container, or pretrained artifact | SBOM, CVE/container scanning, model signing, **pinned/vetted deps from internal mirror** (egress off) |

> **The low-and-slow special case.** Classes B and C converge in the *gradual baseline poisoning*
> attack: an insider drifts their own "normal" over months so an absolute baseline never alarms. This
> is countered structurally, not patched: **long observation windows**, **peer-group anchoring**,
> **change-point detection**, and **periodic human-reviewed baseline resets** (Part 15). It is treated
> as a recurring *vulnerability class*, re-tested in every red-team cycle (`security/reports/redteam.md`).

---

## 6. Residual risk & accepted limitations (honest)

A regulator-grade model states what it does **not** fully solve (Part 15):

- **Collusion & dual-control defeat.** Two honest-looking people defeating maker-checker, or an
  executive override, are only *partly* in reach of any model. Hawk-Eye raises the cost and surfaces
  the graph-level signal (L5), but it **complements** whistleblowing, surprise audit, SoD, and board
  oversight — it does not replace them.
- **Adversarial insiders with deep knowledge.** A sufficiently informed Class-C subject can probe
  the boundary. The diverse ensemble + randomized review + hidden logic raise the bar; recurring
  adversarial-ML testing keeps measuring it. Residual risk is **accepted and monitored**, not eliminated.
- **Privacy / surveillance / fairness of monitoring staff.** Mitigated by proportionality, DPIA
  (DPO-2026-004), transparency to staff/works-council, fairness testing (Part 29), strict RBAC, and
  the **natural-justice HITL gate** before any classification — but it remains a standing
  legal/cultural risk that governance, not engineering alone, must hold.
- **Synthetic-only evaluation.** The pilot is synthetic; detection quality must be re-validated
  against real labeled outcomes before production reliance (Part 14). Tracked as an MRM limitation in
  `security/reports/model-risk.md`.

These residuals feed the model-risk register (`security/reports/model-risk.md`), the red-team residual
list (`security/reports/redteam.md`), and the vuln tracker (`security/vuln-mgmt/`).

---

## 7. How this threat model is exercised (continuous, not one-off)

- **Threat modeling per release** (Part 19.4) — this document is re-reviewed each model release; the
  current release under review is **`fusion-2026.2.0`**.
- **Penetration testing** of the platform/APIs/dashboard → `security/reports/vapt.md` (passed; CISO +
  external vendor sign-off; **zero unremediated critical**).
- **ATLAS-based red-teaming** of the deployed models (evasion / poisoning / inversion / extraction) →
  `security/reports/redteam.md` (passed; Red Team + Model Risk sign-off).
- **Periodic model-risk review** tied to the model version → `security/reports/model-risk.md` (Part 13,
  Part 27; Model Risk Committee sign-off).
- **Adversarial-ML evaluation as a recurring control** (Part 19.5) — evasion/poisoning re-tested on a
  cadence; findings risk-ranked into `security/vuln-mgmt/` with patch SLAs (critical ≤ 7 days).
- **SIEM detection of attacks on the system** (Part 19.5) — extraction-pattern querying, abnormal
  label edits, training-data anomalies, and config/threshold changes are monitored like any other
  crown-jewel asset (`security/siem/`).

> The mapped frameworks (MITRE ATLAS, OWASP ML Top 10 / OWASP Top 10, NIST AI RMF, NIST CSF, RBI
> cyber directions) and the FREE-AI 7-Sutra → control map are in **`security/framework-mapping.md`**.
