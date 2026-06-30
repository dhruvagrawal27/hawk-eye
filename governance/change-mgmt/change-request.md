# Change Request Workflow (PLATFORM-19, blueprint Part 31.3 — RBI ITGRCA)

Formal change management for production changes (incl. **rule/threshold changes** — a rule
change can blind detection, so it is treated like a model change with four-eyes approval).

## Workflow
1. **Raise CR** — requester files a change request (template below) + the risk-assessment form.
2. **Risk assessment** — `risk-assessment-form.md`; classify impact/likelihood.
3. **CAB approval** — Change Advisory Board approves production changes (HUMAN step; recorded
   in the governance DB `approvals`, artifact_type=`cab_change`, e.g. CAB-2026-033). SCAFFOLD.
4. **Scheduled window** — deploy only within an allowed window (`python tools/release/release.py
   window-check`); emergency path for criticals.
5. **Deploy** — GitOps via ArgoCD (cd.yml), canary + SLO-gated rollback.
6. **Rollback ready** — `rollback-runbook.md` attached before deploy.
7. **Audit** — every step logged (who/when/what), immutable.

## CR template
| Field | Value |
|---|---|
| CR id | CR-YYYY-NNN |
| Title | |
| Type | code / rule / threshold / model / config / infra |
| Requested by / date | |
| Risk class (from form) | low / medium / high |
| Window | (must be an allowed scheduled window) |
| Rollback plan | (link rollback-runbook.md) |
| CAB decision / resolution | (approved/rejected, CAB-YYYY-NNN) |
