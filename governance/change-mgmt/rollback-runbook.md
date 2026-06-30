# Rollback Runbook (PLATFORM-19, Part 31.3)

Every production change ships with a tested rollback. Auto-rollback also triggers on SLO
regression during canary (cd.yml reads observability/slo-definitions.yaml).

## Automatic (preferred)
- Canary detects SLO breach (p99 latency / availability / error-budget) → ArgoCD rolls back
  to the previous known-good revision automatically. No human in the hot path.

## Manual
1. Identify the bad revision: `argocd app history hawk-eye-<env>`.
2. Roll back: `argocd app rollback hawk-eye-<env> <good-revision>`.
3. For model changes: re-point serving to the previous signed model version (champion).
4. For rule/threshold changes: revert the change-controlled rule set (four-eyes).
5. Validate: smoke (`make topology-smoke`), SLO dashboards green, degradation not stuck on.
6. Post-mortem: `ops/incident-mgmt/runbooks/postmortem-template.md` (blameless).

## Data/DB changes
Restore from immutable backup if needed (`ops/backup/restore.sh`); validate row counts.
