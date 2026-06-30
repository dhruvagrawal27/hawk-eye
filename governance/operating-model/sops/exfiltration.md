# SOP — Data Exfiltration Investigation (PLATFORM-39)

> Blueprint **Part 33.3** (per-typology SOP) + **Part 6** (signal: *off-hours bulk download /
> bulk export before resignation*; `leaver_flag`/notice period is the highest-value insider
> context). **ALERT-ONLY:** ends in a human decision; never auto-blocks.

## 1. Trigger (what fired)
A Hawk-Eye alert on **anomalous bulk data access/export** — large `db_select`/`export`
volume, off-hours, on sensitive datasets, often correlated with **HR joiner-mover-leaver**
context (employee in notice period / `leaver_flag` set). May combine L4 (sequence/time-series
drift, off-hours) + L1 hard rule (off-hours privileged export).

## 2. EDD steps
1. **Read the explanation** — which rule + LAXCAT temporal/variable attention drove it; the
   volume vs the actor's peer-group baseline (Part 6 peer deviation).
2. **Reconstruct the access timeline** (actor→action→object): `login` → `db_select`/`export`
   sequence, datasets touched, volume, time-of-day, channel, destination if observable.
3. **Overlay HR context** — is the actor in notice period / flagged leaver? Recent role change?
   Bulk export shortly before resignation is the classic exfiltration pattern.
4. **Assess sensitivity** — what data class (PII/sensitive/operational) was touched? Was it
   within the actor's legitimate need-to-know, or outside their role (peer deviation)?
5. **Check for staging** — repeated sub-threshold pulls (low-and-slow), use of
   shared/service/orphaned accounts, or movement to removable/cloud egress.
6. **Corroborate** — any approved business reason (migration, reporting)? Consult the line
   manager via the RACI Consulted path without alerting the subject.

## 3. Evidence collection
- Pull `login`/`db_select`/`export` events, dataset IDs, volumes, timestamps, and the HR
  leaver flag from the **immutable WORM audit log**; capture PAM-session evidence if privileged.
- Snapshot the LAXCAT attention + sequence evidence and the peer-group baseline for the file.
- Record chain-of-custody; preserve forensic artifacts (do not let the subject wipe traces —
  loop in Security/SRE per RACI 2.5 if active exfiltration is suspected).

## 4. Disposition (human decides)
- **True fraud/exfiltration** → request-block of further access via HITL gate; isolate the
  account with Security; open case.
- **False positive** → close-as-FP (approved migration/reporting).
- **Inconclusive** → hold; increase monitoring on the actor.
- Capture as a label; disposition within TAT.

## 5. Escalation
Active/large exfiltration or a leaver in notice period → **Senior Investigator + Vigilance +
Security (Incident Response, RACI 2.5)** immediately; if a personal-data breach, the **CISO/DPO
breach-notification workflow** (`SEC-2026-021`) triggers **CERT-In 6-hour** + RBI + DPB notice.

## 6. Handoff — HR disciplinary + law-enforcement referral
- **HR disciplinary:** evidence package to HR (timeline + attention evidence + audit extract);
  natural justice / due process before adverse action; coordinate with the leaver process.
- **Law-enforcement referral:** **CBI / ED** as warranted; if customer PII was exfiltrated,
  the DPDP breach + CERT-In paths run in parallel; Vigilance co-signs; Legal Consulted.
- Feed novel exfiltration tradecraft into `km-wiki.md` → rule + synthetic-library scenario.
