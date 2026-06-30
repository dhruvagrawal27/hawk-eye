# Hawk-Eye Runbooks — Index

> **Owner:** PLATFORM (Laptop 06) · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 30** (Reliability — HA/DR/BCP/SRE), **Part 34.3**
> (Documentation & knowledge assets — "Runbooks & ops manuals … all version-controlled and
> audit-accessible").

This directory is the **entry point** for operating Hawk-Eye. Runbooks are version-controlled,
audit-accessible, and split by purpose. **Golden rule:** Hawk-Eye is **alert-only** — no runbook
here auto-blocks money; the worst the platform does on its own is **degrade to rules-only**
(a continuity feature, Part 18 / 30.1).

---

## Runbooks in this directory

| Runbook | Purpose | Blueprint |
|---|---|---|
| [`ops-manual.md`](./ops-manual.md) | Day-to-day operations: start/stop the stack via `make`, health checks, common ops, the degradation switch, the service/port map | Part 30.2, CONTEXT.md §7 |

## Runbooks that live elsewhere (cross-references)

| Runbook | Location | Purpose | Blueprint / Task |
|---|---|---|---|
| **DR failover** | [`/ops/dr/runbooks/failover-runbook.md`](../../ops/dr/runbooks/failover-runbook.md) | Documented, rehearsed disaster-recovery failover — steps, roles, validation, `make dr-drill` evidence | Part 30.1 · PLATFORM-27 |
| **RTO/RPO matrix** | [`/ops/dr/rto-rpo-matrix.md`](../../ops/dr/rto-rpo-matrix.md) | Per-component recovery objectives the failover runbook validates against | Part 30.1 · PLATFORM-25 |
| **Incident response** | [`/ops/incident-mgmt/runbooks/incident-response.md`](../../ops/incident-mgmt/runbooks/incident-response.md) | Severity levels, incident-commander role, comms, RBI/CERT-In **6-hour** reporting | Part 30.2 · PLATFORM-30 |
| **Post-mortem template** | [`/ops/incident-mgmt/runbooks/postmortem-template.md`](../../ops/incident-mgmt/runbooks/postmortem-template.md) | The **blameless** post-mortem template | Part 30.2 · PLATFORM-30 |
| **Backup / restore** | [`/ops/backup/`](../../ops/backup/) | Encrypted, immutable, object-lock backups + restore scripts | Part 30.1 |

---

## How runbooks fit the operating model

- **On-call.** Operational alerts (pipeline lag, drift, node down) route to an on-call rotation by
  severity via `ops/oncall/alertmanager.yml` (Alertmanager :9093). Critical cyber incidents also
  fan out to the **regulatory-reporting** receiver (RBI / CERT-In, 6h — Part 28.1).
- **Three Lines of Defense (Part 33.1).** SRE/Platform runs these runbooks (1st-line *operations*);
  Security drives incident response; Internal Audit reads them for assurance.
- **Change management (Part 31.3).** Any change to *what these runbooks operate on* (rules,
  thresholds, model versions, infra) is change-controlled with CAB sign-off (seeded approvals in
  the governance DB, e.g. **CAB-2026-033**).

---

## Conventions used across all runbooks

- **Status legend** (CONTEXT.md §3): **REAL** (works on synthetic/mock data locally) ·
  **SCAFFOLD** (needs a real external resource — cloud creds, HSM/TEE, a human validator) ·
  **MOCK** (a stand-in for a human/legal/hardware act; the *script + report* are real evidence).
- **Time:** UTC ISO-8601 in artifacts; display in IST.
- **Commands:** all driven through the root **`Makefile`** (`make help` lists every target).

---

*Source of truth: blueprint Part 30 + Part 34.3. The service/port map is maintained by PLATFORM in
CONTEXT.md §7.*
