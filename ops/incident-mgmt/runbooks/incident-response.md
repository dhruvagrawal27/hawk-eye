# Incident Response Runbook (PLATFORM-30, blueprint Part 30.2 + Part 28.1)

> Severity tiers, the incident-commander role, comms, and the **RBI/CERT-In reporting**
> step (CERT-In **6-hour** rule, Part 28.1). Operational alerts route here via Alertmanager
> (`ops/oncall/alertmanager.yml`). Blameless post-mortems: `postmortem-template.md`.

## Severity tiers
| Sev | Definition | Response | Reporting |
|---|---|---|---|
| **SEV-1** | Pipeline down / data loss / confirmed breach of the crown-jewel system | Page IC + on-call immediately; war-room | **CERT-In ≤6h**; RBI cyber-incident; DPB + principals if personal-data breach |
| **SEV-2** | Degraded (rules-only stuck, drift, partial outage) | On-call + IC; fix within SLA | Internal; RBI if material |
| **SEV-3** | Minor / single-component, no customer/regulatory impact | On-call; next business day | Internal log |

## Roles
- **Incident Commander (IC)** — owns the incident, decisions, timeline (not hands-on-keyboard).
- **Ops/SRE + Security** — remediation.
- **Comms** — internal + regulator liaison.
- **Scribe** — timeline for the post-mortem.

## Flow
1. **Detect** — Alertmanager (pipeline lag / drift / node-down / SIEM attack signature) or a report.
2. **Triage & declare** severity; assign IC; open the incident channel + scribe doc.
3. **Distinguish** (critical): is this a **personal-data breach** (DPDP → Data Protection Board +
   affected principals) vs a **general cyber incident** (CERT-In 6h + RBI)? They have different
   obligations (Part 28.1) — see `governance/docs/breach-notification.md`.
4. **Contain → eradicate → recover.** If reliability: invoke `ops/dr/runbooks/failover-runbook.md`.
   If an attack on the system: the SIEM detectors (`security/siem/`) scope it.
5. **Regulatory clock:** SEV-1 cyber → **file CERT-In within 6 hours**; notify RBI; if PII →
   DPB + principals. Record in governance DB `incidents` (reported_to, report_deadline).
6. **Resolve & verify** — SLOs green, `make topology-smoke`, audit intact.
7. **Blameless post-mortem** within 5 business days (`postmortem-template.md`); feed actions
   back into runbooks + the threat-intel loop (Part 34.5).

## ALERT-ONLY note
No incident response auto-blocks money or auto-classifies fraud — the HITL gate (PLATFORM-37)
and degradation switch keep the system alert-only throughout (golden rule #1).
