# Vulnerability Assessment & Penetration Test (VAPT) Report — Hawk-Eye (PLATFORM-23, MOCK)

> **MOCK / SYNTHETIC REPORT.** This is a *synthetic* assurance artifact for the Hawk-Eye pilot. No
> real penetration test was performed against a production system; findings, hosts, and identifiers
> are illustrative and exercise only the **synthetic, alert-only, on-prem-capable** Hawk-Eye build.
> Its purpose is to demonstrate the VAPT control and seed the governance evidence chain.
>
> **Blueprint:** Part 19.4 (penetration testing, secure-SDLC), Part 19.3 (platform/infra security),
> Part 19.5 (vulnerability-management programme). **Task:** PLATFORM-23. **Status:** MOCK — **VAPT
> PASSED**.
>
> **Feeds:** `security/vuln-mgmt/` (PLATFORM-22 vuln tracker) and the governance DB
> `security_reports` row (`report_type=vapt`, already seeded). **Cross-references:**
> `security/threat-model.md`, `security/framework-mapping.md`, `security/zero-trust-policy.md`,
> `security/admin-access-policy.md`.

---

## 0. Report metadata (matches governance DB `security_reports` seed)

| Field | Value |
|---|---|
| Report type | `vapt` |
| Scope | **platform + APIs + dashboard** |
| Model version under review | **fusion-2026.2.0** |
| Findings (total) | **12** |
| Critical findings | **0** |
| Unremediated critical | **0** |
| Status | **passed** |
| Sign-off | **External VAPT vendor + CISO** |
| Report date | **2026-05-08** |
| Report path | `security/reports/vapt.md` |
| Region / residency | ap-south-1 / in-india |
| Deploy target (pilot) | AWS Lightsail (ADR-0001 — documented deviation from Part 26 EC2-in-VPC; production = on-prem in-India) |

---

## 1. Executive summary

An independent VAPT was performed against the Hawk-Eye **platform, APIs, and investigator dashboard**
ahead of the `fusion-2026.2.0` go-live review. The assessment covered the six zero-trust zones, the
backend/governance APIs, the investigator dashboard, the model-serving path, the TEE-attested LLM
gateway egress, and the privileged-access (PAM) workflow.

**Verdict: PASSED.** Twelve findings were identified — **zero critical**, two high (both remediated
and retested), seven medium, three low/informational. There are **no unremediated critical findings**
and no finding that breaks the system's golden rules (alert-only, no internet egress beyond the two
LLM hosts, no real PII in the synthetic build). All high/medium findings were remediated and
retested; residual low/informational items are accepted with documented compensating controls and
tracked in `security/vuln-mgmt/`.

Notably, the **zero-trust posture held under test**: the assessor could not reach the data zone
(Postgres/ClickHouse/MinIO/Kafka) from the edge, could not exfiltrate to any host other than the two
pinned LLM FQDNs, and could not act as an admin without going through the PAM broker. The most
material findings were *application-layer* (authz edge cases, headers, rate-limit gaps), not
architectural.

---

## 2. Scope

### 2.1 In scope
- **Platform / infrastructure:** the six security zones (edge, app, data, compute/serving,
  governance, management), `NetworkPolicy` + SG/NACL enforcement, the NAT FQDN egress allow-list,
  mTLS/SPIFFE service identity, secrets-by-reference (Vault).
- **APIs:** `backend` (8000), `governance-api` (8093), `hitl-gate` (8094), `serving` (8001, KServe
  v2 inference), `tee-attestation` (8090), `pam-shim` (8091), `degradation-switch` (8092).
- **Dashboard:** investigator frontend (5173) — triage queue, entity-360, explanation panel,
  disposition flow; RBAC + need-to-know; session controls.
- **Identity:** Keycloak (8080) OIDC, MFA, SoD role bindings; PAM break-glass path.

### 2.2 Out of scope (and why)
- **Live fund-movement / core-banking systems** — Hawk-Eye is **alert-only** and does not touch
  money; nothing to test there by design.
- **Real PII / production data** — the build is **synthetic only**; no real personal data exists in
  the pilot.
- **The external LLM providers' internals** (NEAR AI, Groq) — third-party; covered by vendor due
  diligence + TEE attestation verification, not by this pen-test. Egress *to* them was tested.

### 2.3 Rules of engagement
Black-box + authenticated grey-box, against a non-production replica of the Lightsail pilot. No DoS
against shared infra; no destructive tampering of the WORM audit log (its tamper-evidence was
verified read-only). Test window 2026-04-28 → 2026-05-06; retest 2026-05-07 → 2026-05-08.

---

## 3. Methodology

Aligned to **OWASP Top 10 / OWASP ASVS**, **OWASP API Security Top 10**, **PTES**, **NIST SP 800-115**,
and Hawk-Eye's own threat model (`security/threat-model.md`) and framework map
(`security/framework-mapping.md`). Phases:

1. **Reconnaissance & enumeration** — surface mapping, port/zone enumeration, TLS/cert inspection.
2. **Network & segmentation testing** — attempt edge→data, data→internet, cross-zone lateral
   movement; verify default-deny and the egress allow-list.
3. **Authentication & session** — OIDC/MFA, token handling, session fixation/timeout, RBAC bypass.
4. **Authorization (BOLA/BFLA)** — need-to-know enforcement (can analyst A read analyst B's cases?),
   SoD persona boundaries (can a labeler self-grant builder/actor?).
5. **API abuse** — input validation, injection, mass-assignment, rate-limiting (incl. the
   inference API anti-extraction posture).
6. **Secrets & crypto** — secrets-by-reference, mTLS enforcement, PII tokenization-before-egress.
7. **PAM / privileged path** — admin access only via `pam-shim`, session recording, four-eyes.
8. **Audit integrity** — WORM append-only behaviour; "watch-the-watchers" coverage.
9. **Retest** — re-validate all remediated findings.

CVSS v3.1 base scores; severities risk-ranked per Part 19.5 (patch SLA: critical ≤ 7 days).

---

## 4. Findings (CVSS-scored)

**Summary: 12 findings — Critical 0 · High 2 · Medium 7 · Low/Info 3.** All High/Medium remediated +
retested; Low/Info accepted with compensating controls.

| ID | Title | Severity (CVSS) | Component | Status |
|---|---|---|---|---|
| HE-VAPT-001 | BFLA: `governance-api` allowed a non-admin role to read another analyst's case metadata | **High (7.1)** | `governance-api` (8093) | **Remediated · retested PASS** |
| HE-VAPT-002 | Inference API lacked per-principal rate limiting (model-extraction enabler) | **High (7.4)** | `serving` (8001) | **Remediated · retested PASS** |
| HE-VAPT-003 | Missing security headers (CSP, HSTS, X-Content-Type-Options) on dashboard | Medium (5.3) | frontend (5173) | Remediated · retested PASS |
| HE-VAPT-004 | Verbose API error messages leaked stack/version info | Medium (5.0) | `backend` (8000) | Remediated · retested PASS |
| HE-VAPT-005 | Session timeout longer than policy on idle investigator sessions | Medium (4.8) | Keycloak (8080) | Remediated · retested PASS |
| HE-VAPT-006 | `degradation-switch` state-change endpoint accepted single-actor toggle (four-eyes gap) | Medium (6.1) | `degradation-switch` (8092) | Remediated · retested PASS |
| HE-VAPT-007 | Re-identification (unmask) action under-logged in WORM trail | Medium (5.9) | `backend` / vault path | Remediated · retested PASS |
| HE-VAPT-008 | Outdated dependency with known CVE in a transitive package | Medium (5.4) | build (SBOM) | Remediated (pinned via internal mirror) · retested PASS |
| HE-VAPT-009 | Permissive CORS on a non-prod governance route | Medium (4.3) | `governance-api` (8093) | Remediated · retested PASS |
| HE-VAPT-010 | TLS config allowed one legacy cipher on an internal listener | Low (3.7) | mTLS layer | Remediated · retested PASS |
| HE-VAPT-011 | Username enumeration via login-timing difference | Low (3.1) | Keycloak (8080) | Accepted (MFA + lockout compensate) · tracked |
| HE-VAPT-012 | Informational: clickjacking — missing `frame-ancestors` (covered once CSP added) | Info (0.0) | frontend (5173) | Resolved with HE-VAPT-003 |

> **No finding reached Critical.** The two High findings were *application-layer* authorization /
> rate-limit gaps, not architectural — the zero-trust segmentation, no-egress posture, mTLS, and PAM
> brokering all held throughout.

### 4.1 Detail — HE-VAPT-001 (High, BFLA → fixed)
**Observation.** A read endpoint on `governance-api` keyed off the case ID without re-checking the
caller's need-to-know binding, so a logged-in non-admin could enumerate case metadata they were not
assigned. **Impact.** Confidentiality (NIST CSF PROTECT; OWASP API1/BOLA). **Remediation.**
Object-level authorization re-check against the analyst's assignment + SoD role on every read; added
a regression test and a WORM audit entry on every access. **Retest.** Enumeration attempt now returns
403 and is logged. **Status: PASS.**

### 4.2 Detail — HE-VAPT-002 (High, extraction enabler → fixed)
**Observation.** The internal inference API (`serving` :8001) had no per-principal rate limit; while
internal-only and authenticated, a compromised account could issue extraction-pattern queries
(maps to ML-attack family §1.3/§1.4, `framework-mapping.md`). **Remediation.** Per-principal token
bucket + extraction-pattern anomaly detection wired to `security/siem/`; raw scores never exposed
externally. **Retest.** Burst querying is throttled and alerted. **Status: PASS.**

---

## 5. Remediation summary & SLA compliance

| Severity | Found | Remediated | Accepted (compensated) | Patch SLA (Part 19.5) | Met? |
|---|---|---|---|---|---|
| Critical | 0 | — | — | ≤ 7 days | n/a (none) |
| High | 2 | 2 | 0 | ≤ 14 days | Yes (within window) |
| Medium | 7 | 7 | 0 | ≤ 30 days | Yes |
| Low / Info | 3 | 1 | 2 | ≤ 90 days | Yes |

Remediated dependency CVE (HE-VAPT-008) was patched via the **internal vetted mirror** (egress is
off in the running system — Part 19.5). Accepted low/info items carry documented compensating
controls and are tracked in `security/vuln-mgmt/` with risk acceptance recorded.

---

## 6. Retest & sign-off

All High and Medium findings were **remediated and retested** in the 2026-05-07 → 2026-05-08 window
and confirmed closed. Two low/informational items are formally **risk-accepted** with compensating
controls. **There are zero unremediated critical findings.**

| Role | Party | Decision | Date |
|---|---|---|---|
| Independent assessor | **External VAPT vendor** | VAPT complete — pass | 2026-05-08 |
| Accountable owner | **CISO** | Accepted; cleared for go-live review | 2026-05-08 |

> **Sign-off:** *External VAPT vendor + CISO* — matching the governance DB `security_reports` row
> (`report_type=vapt`, `status=passed`, `findings_count=12`, `critical_count=0`,
> `signoff="External VAPT vendor + CISO"`, `model_version=fusion-2026.2.0`, `report_date=2026-05-08`).

---

## 7. Linkage

- **Model risk:** companion `security/reports/model-risk.md` (periodic review, `fusion-2026.2.0`).
- **Adversarial ML:** companion `security/reports/redteam.md` (ATLAS evasion/poisoning/inversion/extraction).
- **Vuln tracker:** open/accepted items flow to `security/vuln-mgmt/` (PLATFORM-22) with patch SLAs.
- **Go-live evidence:** this report satisfies the go-live item *"VAPT + adversarial-ML red-team passed"*
  (`security_reports report_type=vapt;status=passed`).
