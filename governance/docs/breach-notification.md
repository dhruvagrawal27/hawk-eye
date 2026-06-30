# Breach & Incident Notification Workflow — Hawk-Eye

> **Workstream:** PLATFORM-36 (policy / regulatory documentation).
> **Blueprint basis:** Part 28.1 (personal-data breaches to the **Data Protection Board +
> affected principals**; coordinate with **CERT-In 6-hour rule** and RBI cyber-incident
> reporting; **distinguish personal-data breaches from general cyber incidents**), Part 30.2
> (incident management), Part 19 (security).
> **Regulators in scope:** DPDP Act 2023 + Rules 2025, CERT-In Directions 2022 (6-hour
> reporting), RBI Cyber Security Framework 2016, RBI ITGRCA MD 2023, RBI Fraud Risk Management
> MD 2024.
> **MOCK status:** the workflow approval is a human act; the **record** is seeded in the
> governance DB (`policies` where `policy_type='breach'`). Incidents are logged in the
> `incidents` table.

---

## Approval block (seeded governance record)

| Field | Value |
|---|---|
| Policy name | Breach-Notification Workflow |
| Policy type | `breach` |
| Status | `board_approved` |
| Approved by | **CISO + DPO** |
| Approval date | **2026-03-10** |
| Resolution | **SEC-2026-021** |
| Evidence record | `policies` (`resolution_id='SEC-2026-021'`); incidents logged in `incidents` (`incident_type`, `reported_to`, `report_deadline`) |

**Signatories:** Chief Information Security Officer and Data Protection Officer, recorded as
resolution **SEC-2026-021** dated 2026-03-10.

---

## 1. The core distinction — personal-data breach vs general cyber incident

A single event can be one, the other, or **both**. The triage gate below classifies every
event **first**, because the obligations and clocks differ.

| | **Personal-data breach** | **General cyber incident** |
|---|---|---|
| Definition | Unauthorised access, disclosure, alteration, loss or destruction of **personal data** | A cyber-security event (intrusion, DoS, malware, ransomware, defacement, etc.) with no confirmed personal-data exposure |
| Lead owner | **DPO** | **CISO** |
| Notify | **Data Protection Board (DPB)** + **affected data principals** + (if also cyber) CERT-In + RBI | **CERT-In** (6h) + **RBI** (cyber framework) |
| Primary clock | DPB & principal notification per DPDP Rules timelines | **CERT-In 6-hour** rule |
| Both at once | Yes — a cyber intrusion that exfiltrates PII is **both**; run both tracks in parallel | — |

> **Rule:** if personal data is (or may be) involved, the **DPO track is mandatory** even when
> the CISO is leading the cyber response. If a cyber-security event is in scope of CERT-In, the
> **6-hour clock starts at detection regardless** of whether personal data is involved.

---

## 2. Notification matrix (who, what, when)

| Recipient | Triggered by | Deadline | Owner | Content |
|---|---|---|---|---|
| **CERT-In** | Any reportable cyber incident (CERT-In Directions) | **Within 6 hours of detection** | CISO | Incident type, timestamps, affected systems, indicators, actions taken |
| **Data Protection Board (DPB)** | Confirmed/suspected personal-data breach | Per DPDP Rules timelines (without undue delay) | DPO | Nature, categories & approximate volume of data, likely consequences, mitigations |
| **Affected data principals** | Personal-data breach affecting identifiable individuals | Per DPDP Rules (without undue delay) | DPO | What happened, likely impact, steps taken, what they should do, grievance contact |
| **RBI** | Cyber incident / material fraud incident | Per RBI Cyber Framework 2016 / Fraud MD 2024 timelines | CISO / MLRO | Incident detail, impact, containment, regulatory category |
| **Internal — Board / ISC / AMRC** | Any sev-1 incident; any AI-model incident | Immediate escalation | Incident Commander | Status, impact, decisions, regulatory clocks running |

> **AI-model incidents** (e.g., a Tier-1 model behaving anomalously, bias detection, an
> attestation failure on the LLM gateway) use **FREE-AI's indicative AI incident-reporting form**
> and are logged with `incident_type='ai_model'`. They feed the AMRC and, where personal data or
> a cyber dimension exists, the DPB/CERT-In tracks.

---

## 3. End-to-end workflow

```
[Detection] (SIEM / monitoring / report)
     │
     ▼
[Triage gate] ── classify ──► personal-data breach? ── yes ──► open DPO track
     │                         cyber incident?       ── yes ──► open CISO/CERT-In track
     │                         AI-model incident?    ── yes ──► FREE-AI form → AMRC
     ▼
[Severity + Incident Commander assigned] (Part 30.2 sev tiers)
     │
     ├─► CERT-In track:  contain → report to CERT-In within 6h → RBI as required
     │
     ├─► DPO track:      assess scope/volume → notify DPB → notify affected principals → grievance support
     │
     └─► AI track:       FREE-AI incident form → AMRC review → model action (rollback / degrade to rules)
     │
     ▼
[Containment & eradication] ─► [Recovery] ─► [Blameless post-mortem (Part 30.2)] ─► [Close + update incidents table]
```

Every step writes to the **immutable audit log**; the `incidents` table records
`incident_type`, `severity`, `reported_to`, `report_deadline` (e.g., `CERT-In 6h`), and
open/close timestamps.

---

## 4. Roles

| Role | Responsibility |
|---|---|
| **Incident Commander** (SRE/Security) | Runs the response; owns the timeline and the regulatory clocks |
| **CISO** | Owns the cyber/CERT-In/RBI cyber track; accountable for the 6-hour report |
| **DPO** | Owns the personal-data-breach/DPB/principal track; assesses scope and consequences |
| **MLRO / Compliance** | RBI fraud-incident reporting; regulatory liaison |
| **AMRC** | Reviews AI-model incidents (FREE-AI form); decides model action |
| **Legal / HR** | Affected-principal communications; employment-context handling |
| **Board / ISC** | Receive sev-1 escalation; oversight |

---

## 5. Templates

### 5.1 CERT-In 6-hour report (skeleton)
```
Reporting entity: <Bank>          Contact (CISO): <name/desk>
Detection timestamp (IST): <ts>   Report timestamp (IST): <ts>  (must be ≤ 6h)
Incident category (CERT-In): <e.g., unauthorised access / ransomware / data breach>
Affected systems: <list>          Indicators of compromise: <IOCs>
Impact summary: <...>             Actions taken / containment: <...>
Personal data involved? <yes/no>  → if yes, DPO track also open (ref incident id)
```

### 5.2 DPB personal-data-breach notification (skeleton)
```
Data Fiduciary: <Bank>            DPO contact: <name>
Nature of breach: <unauthorised access / disclosure / loss / alteration>
Categories of personal data: <identity / behavioural / financial / derived>
Approximate number of principals affected: <n>
Likely consequences: <...>        Mitigations applied / proposed: <...>
Status of affected-principal notification: <pending / sent>
```

### 5.3 Affected-principal notice (skeleton)
```
Dear <principal>,
We are writing to inform you of a data incident affecting your personal data.
What happened: <plain-language>   What data was involved: <...>
Likely impact on you: <...>       What we have done: <...>
What you should do: <...>         How to reach us / raise a grievance: <DPO contact channel>
```

---

## 6. Cross-references
- DPIA (risk basis): `governance/docs/dpia.md` (DPO-2026-004).
- DPO appointment & grievance contact: `governance/docs/dpo-appointment.md`.
- Lawful-basis map: `governance/docs/lawful-basis-map.md` (DPO-2026-003).
- AI Policy (AI incident reporting obligation): `governance/docs/ai-policy.md` (BR-2026-014).
- Reliability / incident management: `governance/bcp.md` (BRC-2026-008), Part 30.2.
