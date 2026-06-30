# Blameless Post-Mortem — INCIDENT-<id> (PLATFORM-30, blueprint Part 30.2)

> Blameless: focus on **systems and processes, not individuals**. Complete within 5 business
> days of resolution. Feeds corrective actions back into runbooks + the threat-intel loop
> (Part 34.5). Reviewed by SRE/Security; SEV-1s reported to the Board.

## Summary
- **Incident id / title:**
- **Severity:** SEV-_ · **Detected:** <ts> · **Resolved:** <ts> · **Duration:**
- **Incident Commander:** · **Scribe:**
- **Customer/regulatory impact:** (and whether CERT-In/RBI/DPB were notified — Part 28.1)

## Timeline (UTC)
| Time | Event |
|---|---|
| | detection (how — Alertmanager / SIEM / report) |
| | declaration + IC assigned |
| | mitigation steps |
| | resolution + validation (`make topology-smoke`, SLOs green) |

## What happened
(Factual narrative.)

## Impact
- SLOs breached? error budget burned (`observability/slo-definitions.yaml`)?
- Data loss / RPO actual vs target (`ops/dr/rto-rpo-matrix.md`)?

## Root cause(s)
(5-whys / contributing factors — systemic, not personal.)

## What went well / what didn't
- Well:
- Didn't:

## Corrective actions (tracked to closure)
| Action | Owner | Due | Type |
|---|---|---|---|
| | | | detect / prevent / mitigate / process |

## Lessons → feed the loop
- Runbook updates: ______
- New SIEM rule / threshold (`security/siem/`): ______
- New typology → BACKEND rules + DATA synthetic library (threat-intel hand-off, Part 34.5): ______
