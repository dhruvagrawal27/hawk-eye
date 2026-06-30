# Hawk-Eye Framework Mapping — MITRE ATLAS · OWASP · NIST · RBI · FREE-AI 7 Sutras (PLATFORM-20)

> **Purpose.** Map Hawk-Eye's threats and controls onto the external frameworks a PSB regulator and
> an independent validator will expect: the **ML-attack → MITRE ATLAS → concrete-mitigation** table
> (Part 19.2), plus alignment tables for **OWASP ML Top 10**, **OWASP Top 10**, **NIST AI RMF**,
> **NIST CSF**, and **RBI cyber directions**, and the **FREE-AI 7-Sutra → real-blueprint-control**
> map. Every mitigation cited here is a control that actually exists in the blueprint and/or this repo.
>
> **Blueprint:** Part 19.2 (ML attacks ↔ ATLAS ↔ mitigations), Part 19.4–19.6 (secure-SDLC,
> vuln-mgmt, governance), Part 27.1 (FREE-AI 7 Sutras + 6 pillars), Parts 20.6/25/29/30 (the
> controls the Sutras map onto). "Frameworks to align to" — Part 19 closing line. **Task:** PLATFORM-20.
> **Status:** DOCUMENTATION (regulator-grade).
>
> **Companion:** `security/threat-model.md` (STRIDE + three attacker classes + trust boundaries).
> **Cross-references:** `security/zero-trust-policy.md`, `security/admin-access-policy.md`,
> `security/vuln-mgmt/`, `security/siem/`, `security/reports/` (the assurance evidence).

---

## 0. Golden-rule alignment

- **ALERT-ONLY.** Framework alignment documents *controls over a scoring-and-explaining system*; no
  mapped control auto-blocks money or auto-classifies fraud. The HITL natural-justice gate is itself
  the control that several frameworks (NIST AI RMF "GOVERN/MANAGE", FREE-AI "Accountability") require.
- **ON-PREM + SYNTHETIC + NO EGRESS.** The mappings assume the air-gapped, synthetic-data posture:
  the only egress is the FQDN-pinned, TEE-attested NEAR AI + Groq path with PII tokenized first
  (`security/zero-trust-policy.md` §4). Vendors in scope: **AWS + NEAR AI + Groq** (ap-south-1,
  residency in-india).
- **VALIDATE-AGAINST-BLUEPRINT.** Each mitigation traces to a blueprint Part; the canonical pilot
  deviation (deploy target = **AWS Lightsail**, ADR-0001) does not alter any control here.

---

## 1. ML-specific attacks → MITRE ATLAS → concrete mitigations (Part 19.2)

MITRE ATLAS is the ATT&CK-equivalent knowledge base for attacks on ML systems (tactics:
Reconnaissance → Resource Development → ... → ML Attack Staging → Exfiltration → Impact). The six
attack families relevant to Hawk-Eye, each with the blueprint's **concrete** mitigations and the
repo control that implements them:

| # | Attack family (ATLAS) | ATLAS tactic / technique anchor | What it looks like for *this* system | Concrete mitigation (Part 19.2) | Implemented in |
|---|---|---|---|---|---|
| 1 | **Evasion / adversarial perturbation** | ML Attack Staging → *Craft Adversarial Data*; Impact → *Evade ML Model* | An insider who knows the model crafts activity to stay just under detection ("insiders know the thresholds") | **Peer-relative** (not absolute) baselines; **don't expose** thresholds/logic; **randomized review sampling**; **ensemble of diverse detectors** (rules + unsupervised + supervised + graph) so evading one doesn't evade all; **adversarial-robustness testing** | L1–L6 ensemble; `security/reports/redteam.md` (evasion probe); peer-baseline design |
| 2 | **Data / label poisoning** | Resource Development → *Poison Training Data*; ML Attack Staging | A privileged user slowly corrupts training data, **poisons the behavioural baseline ("low-and-slow")**, or games the **EDD feedback labels** to teach the model their fraud is "normal" | **Segregate** who touches training data vs who labels vs who builds (SoD); **provenance/lineage** on all training data; **anomaly-check the training set itself**; **peer-anchored + change-point** baselines resist gradual poisoning; **review label distributions** for manipulation; **immutable label audit** | SoD personas (`governance/`); `security/reports/redteam.md` (poisoning probe); data lineage (Part 28.2) |
| 3 | **Model inversion / membership inference** | Exfiltration → *Infer Training Data Membership*; *ML Model Inversion* | Attacker queries/extracts the model to **recover sensitive customer/employee data** | **Restrict inference API** (internal only, authenticated, **rate-limited**); **no raw scores externally**; **differential-privacy / regularization** where feasible; **monitor for extraction-pattern querying** | serving (8001) internal-only; `security/siem/` extraction-pattern rule; Part 19.2 |
| 4 | **Model extraction / theft** | Exfiltration → *Exfiltrate via ML Inference API*; *Steal ML Model* | Stealing the model (IP + enables offline evasion crafting) | Model artifacts **encrypted at rest, signed, access-controlled**; **no model leaves the perimeter**; **access logging on the registry** | MLflow/registry; model signing (Part 19.4); zero-trust no-egress |
| 5 | **Explanation manipulation** | ML Attack Staging → *fool post-hoc explainers* (Slack et al. 2020) | Adversarial "scaffolding" classifiers **fool LIME/SHAP into innocuous explanations** | **Don't rely solely on post-hoc explanations**; prefer **inherently interpretable** components + **rule provenance**; **cross-check explanations against rules and raw evidence**; consider **causal/invariant** methods that resist forged correlations | L1 rule provenance; TreeSHAP + counterfactuals defense-in-depth (Part 20.6) |
| 6 | **ML supply-chain compromise** | **AML.T0048** — *ML Supply Chain Compromise* (Resource Development) | Malicious code/data in a dependency, container, or pretrained artifact | **SBOM**; **dependency/CVE scanning**; **model signing**; **container scanning**; **pinned/vetted deps from an internal mirror** (egress is off) | `ci/security/sbom/`; `security/vuln-mgmt/` (Trivy/Grype/Dependency-Check); internal mirror (Part 19.5) |

> **Reading note.** Families 1–2 are driven mainly by the *subjects* (Class C) and *insiders*
> (Class B); 3–4 by *external* attackers (Class A) and insiders; 5 by insiders/subjects forging
> innocence; 6 by external supply-chain. The attacker-class breakdown is in
> `security/threat-model.md` §5. The recurring discipline (Part 19.5): adversarial-ML evaluation is a
> **vulnerability class, not a one-off** — re-tested every red-team cycle, findings tracked with
> patch SLAs in `security/vuln-mgmt/`.

---

## 2. OWASP ML Security Top 10 alignment

| OWASP ML risk | Hawk-Eye exposure | Control |
|---|---|---|
| **ML01 Input manipulation (evasion)** | Subjects shaping activity under thresholds | §1.1 — diverse ensemble, peer-relative baselines, randomized sampling |
| **ML02 Data poisoning** | Privileged-user training/label corruption | §1.2 — SoD, lineage, training-set anomaly check, immutable label audit |
| **ML03 Model inversion** | Recover employee/customer data from the model | §1.3 — internal rate-limited API, no raw external scores, DP/regularization |
| **ML04 Membership inference** | Determine if a record was in training data | §1.3 — same controls + extraction-pattern monitoring |
| **ML05 Model theft** | IP loss + offline evasion crafting | §1.4 — encrypted/signed artifacts, no egress, registry logging |
| **ML06 Corrupted (AI) supply chain** | Malicious dep/container/pretrained artifact | §1.6 (AML.T0048) — SBOM, CVE/container scanning, signing, internal mirror |
| **ML07 Transfer-learning attack** | Tainted pretrained base (e.g., the gpt-oss LLM) | Vetted/pinned artifacts; LLM is *narrative-only*, validated for grounding/hallucination (Part 25, 27.2) |
| **ML08 Model skewing** | Gaming the EDD feedback loop to skew the model | §1.2 + feedback-loop fairness trap monitoring (Part 29.1) |
| **ML09 Output integrity attack** | Tamper with score/reason code before display | mTLS integrity; deterministic L1–L6; LLM only explains (Part 25.1); WORM audit |
| **ML10 Model poisoning** | Direct tamper of model weights/artifact | Signed artifacts + signature verification on load; encrypted registry (§1.4) |

## 3. OWASP Top 10 (web/application) alignment — the platform & dashboard

| OWASP Top 10 (2021) | Hawk-Eye control | Where |
|---|---|---|
| **A01 Broken access control** | RBAC + need-to-know (analysts see only assigned cases); SoD personas; least-privilege service accounts | `admin-access-policy.md`; Part 19.3 |
| **A02 Cryptographic failures** | mTLS in transit, encryption + field-level tokenization at rest, HSM/Vault keys, PII HMAC before egress | `zero-trust-policy.md` §5; Part 19.3, 25.3 |
| **A03 Injection** | SAST/DAST in CI; parameterized queries; schema-validated L0 events; WAF | Part 19.4; `ci/` |
| **A04 Insecure design** | Threat-modeling per release; zero-trust default-deny; alert-only + HITL by design | `threat-model.md`; Part 19.1, 19.4 |
| **A05 Security misconfiguration** | IaC scanning; OPA/Conftest residency + zero-trust policy-as-code; pinned configs | `zero-trust-policy.md` §6; Part 19.4 |
| **A06 Vulnerable/outdated components** | SBOM + dependency/CVE scanning gating CI; internal vetted mirror; patch SLAs | `security/vuln-mgmt/`; Part 19.4, 19.5 |
| **A07 Identification & authn failures** | Keycloak OIDC + MFA, named accounts, SPIFFE service identity, PAM for admin | `zero-trust-policy.md` §5; `admin-access-policy.md` |
| **A08 Software & data integrity failures** | Model signing + verify-on-load; signed artifacts; AML.T0048 supply-chain controls | §1.4, §1.6; Part 19.4 |
| **A09 Logging & monitoring failures** | WORM audit of all actions (incl. investigators); SIEM for attacks on the system | Part 19.3, 19.5; `security/siem/` |
| **A10 SSRF** | No general internet egress; FQDN-pinned NAT allow-list (only 2 hosts); default-deny egress | `zero-trust-policy.md` §4 |

## 4. NIST AI RMF (Govern / Map / Measure / Manage) alignment

| NIST AI RMF function | Hawk-Eye realization | Where |
|---|---|---|
| **GOVERN** | Board-approved AI Policy (BR-2026-014); AI/Model Risk Committee; SoD across build/label/act/admin; immutable audit | Part 27.1–27.2; `governance/` |
| **MAP** | Model inventory + risk tiering (L6 fusion = tier-1); intended-use + limitations documented per model card; context = employee monitoring | Part 27.2; `model-risk.md` |
| **MEASURE** | PR-AUC / precision@k (not accuracy); fairness metrics (Part 29); drift/PSI monitoring; adversarial-ML evaluation; independent validation ("effective challenge") | Part 14, 27.2, 29; `model-risk.md`, `redteam.md` |
| **MANAGE** | Drift + outcome monitoring; change/approval workflow (CAB-2026-033); graceful degradation; AI incident reporting; **HITL natural-justice gate** before any classification | Part 27.2, 30; `hitl-gate` (:8094) |

## 5. NIST CSF (Identify / Protect / Detect / Respond / Recover) alignment

| NIST CSF function | Hawk-Eye realization | Where |
|---|---|---|
| **IDENTIFY** | Crown-jewel asset inventory (A1–A8); threat model + trust boundaries; model inventory; vendor/3rd-party risk (AWS/NEAR AI/Groq) | `threat-model.md`; Part 27.2 |
| **PROTECT** | Zero-trust micro-segmentation, mTLS, least-privilege, PAM, encryption/tokenization, SBOM + signing, no egress | `zero-trust-policy.md`; `admin-access-policy.md`; Part 19.3–19.4 |
| **DETECT** | SIEM for extraction-pattern querying, abnormal label edits, training-data anomalies, config/threshold changes; continuous vuln scanning | `security/siem/`; `security/vuln-mgmt/`; Part 19.5 |
| **RESPOND** | Incident management + severity tiers; CERT-In **6-hour** + RBI cyber-incident reporting; AI incident form (FREE-AI) | Part 28.1, 30.2, 27.1 |
| **RECOVER** | HA + DR (Kafka/ClickHouse/serving), immutable backups, tested restore drills (DR-2026-002), board-approved BCP (BRC-2026-008), degradation → rules-only | Part 30.1 |

## 6. RBI cyber & IT-governance directions alignment

| RBI direction | Obligation | Hawk-Eye control |
|---|---|---|
| **RBI Cyber Security Framework (2016)** | Baseline controls, segmentation, monitoring, incident reporting | Zero-trust segmentation; SIEM; CERT-In/RBI incident wiring (Part 19.3, 19.5) |
| **RBI ITGRCA Master Direction (2023)** | Board-approved BCP/DR, tested; capacity assessment by ITSC; vendor-risk/no-SPOF | BCP BRC-2026-008; DR drills; ITSC-2026-009 capacity; multi-AZ/multi-DC (Part 30) |
| **RBI Outsourcing of IT Services (2023)** | Due diligence, audit rights, exit strategy, concentration risk for AWS/NEAR AI/Groq | Vendor register (AWS/NEAR AI/Groq assessed); **AI-specific clauses** (bias, subcontractor-AI, data confidentiality, no-training); on-prem exit (Part 27.1, 28; ADR-0001) |
| **RBI Master Direction on Fraud Risk Management (2024)** | EWS/RFA, CRILC (₹3 cr / 7-day), FMR/CFR, alert-only + natural justice | Slow-lane EWS; alert-only design + HITL gate; FMR/CFR feeds (Part 16) |
| **RBI FREE-AI Framework (2025)** | 7 Sutras + 6 pillars; board-approved AI policy; AI lifecycle governance; AI incident reporting | §8 below; Part 27.1; BR-2026-014 |
| **DPDP Act 2023 + Rules 2025** | DPO, annual DPIA + audit, algorithmic due diligence, 6-month runway, cross-border transfer | DPIA DPO-2026-004; PII tokenization + TEE for transfer; algorithmic risk verification (Part 28) |
| **SR 11-7 (global MRM backbone RBI aligns to)** | Independent validation, effective challenge, model documentation, ongoing monitoring | Independent Model Validation Unit (MV-2026-007); model cards; `model-risk.md` (Part 27.2) |

---

## 7. NIST AI RMF / CSF coverage of the 6 FREE-AI pillars

For completeness, the **6 FREE-AI pillars** (Part 27.1) map to the controls above:

| FREE-AI pillar | Realized by |
|---|---|
| **Infrastructure** | On-prem/air-gapped compute; TEE for the LLM path; HA/DR (Part 30); zero-trust zones |
| **Policy** | Board-approved AI Policy (BR-2026-014); data-governance + retention policy (Part 28) |
| **Capacity** | ITSC capacity assessment (ITSC-2026-009); investigator staffing-to-alert-volume (Part 33) |
| **Governance** | AI/Model Risk Committee; SoD personas; model inventory + lifecycle (Part 27.2) |
| **Protection** | Part 19 cyber/adversarial controls; DPDP privacy; tokenization + encryption |
| **Assurance** | VAPT + ATLAS red-team + independent model validation + DPIA audit (`security/reports/`) |

---

## 8. FREE-AI 7-Sutra → concrete-blueprint-control map (Part 27.1)

Each Sutra maps to a **real control that already exists** in the blueprint and this repo — not an
aspiration. This is the table an RBI examiner uses to confirm Hawk-Eye "demonstrably honours" the
Sutras.

| # | Sutra | Concrete control(s) it maps to | Blueprint Part | Evidence in repo |
|---|---|---|---|---|
| 1 | **Trust** | Deterministic, auditable L1–L6 scoring + per-request **TEE attestation** for the LLM ("zero-trust, prove-it"); independent model validation gives trust its teeth | Part 25.2, 27.2 | `tee-attestation` (:8090); MV-2026-007 sign-off |
| 2 | **People First** | **Proportionality** + transparency to staff/works-council; **DPIA** for employee monitoring; fairness so no group is over-flagged; natural-justice hearing before any classification | Part 28, 29, 19.6 | DPIA **DPO-2026-004**; `hitl-gate` (:8094) |
| 3 | **Innovation** | Adopt deep sequence/graph models **only where they demonstrably beat simple baselines** under honest evaluation ("work smartly"); TEE makes an external LLM defensible | Part 20, 25 | Per-layer technique selection (Part 20.8) |
| 4 | **Fairness** | **Disparate-impact testing** across grade/age/gender/region/tenure; demographic-parity/equal-opportunity metrics monitored continuously; never use protected attributes/proxies; feedback-loop fairness-trap monitoring | **Part 29** | Fairness audit **ETH-2026-006** |
| 5 | **Accountability** | **Immutable (WORM) audit** of every action incl. investigators' own ("watch the watchers") + **HITL** natural-justice gate; SoD personas; PAM for admins | Part 19.3, 29.2 | WORM audit; `admin-access-policy.md`; `hitl-gate` |
| 6 | **Explainability** | **TreeSHAP reason codes + counterfactuals + rule provenance** (defense-in-depth, manipulation-resistant) and the **TEE-attested narrative LLM** that *explains, never decides* | **Part 20.6 + 25** | reason codes; `tee-attestation`; narrative gateway |
| 7 | **Resilience** | HA + DR (Kafka/ClickHouse/serving), immutable tested backups, board-approved **BCP**, and the **degradation switch** → rules-only fallback so the watcher never goes dark | **Part 30** | BCP **BRC-2026-008**; `degradation-switch` (:8092); DR-2026-002 |

> **The through-line.** Every Sutra lands on a control that is implemented, owned, and evidenced —
> Explainability → Part 20.6 + 25, Fairness → Part 29, Accountability → immutable audit + HITL,
> Resilience → Part 30 — closing the loop from RBI FREE-AI principle to running code and to the
> governance DB approval records (BR-2026-014 AI policy, DPO-2026-004 DPIA, BRC-2026-008 BCP,
> CAB-2026-033 change, ETH-2026-006 fairness, MV-2026-007 validation).

---

## 9. Frameworks-to-align-to (Part 19 closing line) — coverage summary

| Framework | Section | Status |
|---|---|---|
| MITRE ATLAS (AI threats) | §1 | Mapped — 6 families incl. AML.T0048; red-team evidence |
| OWASP ML Top 10 | §2 | Mapped — all 10 |
| OWASP Top 10 | §3 | Mapped — A01–A10 |
| NIST AI RMF | §4 | Mapped — Govern/Map/Measure/Manage |
| NIST CSF | §5 | Mapped — Identify/Protect/Detect/Respond/Recover |
| RBI cyber + IT-governance directions | §6 | Mapped — Cyber'16, ITGRCA'23, Outsourcing'23, Fraud-MD'24, FREE-AI'25, DPDP, SR 11-7 |
| RBI FREE-AI 7 Sutras / 6 pillars | §7–§8 | Mapped — each Sutra → real control + repo evidence |
