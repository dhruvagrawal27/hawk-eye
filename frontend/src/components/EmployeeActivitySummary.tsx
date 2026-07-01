/**
 * Employee activity summary — the "who is this person and what have they been doing?" context a
 * senior approver (AGM Vigilance / DGM Compliance) needs *before* approving an alert or permitting a
 * held privileged action. Composes three existing, RBAC-safe sources (no new endpoints):
 *   • Insider-risk index   — the continuous 0–100 risk score + top drivers (GET /entities/{id}/risk-index)
 *   • Recent activity      — the actor's own operational events (GET /entities/{id}/timeline)
 *   • Decision log         — who has viewed / dispositioned / unmasked this entity (GET /audit?entity=)
 * Each block degrades independently (a role without VIEW_AUDIT still sees risk + activity). Lazy:
 * the parent passes `enabled` (e.g. on expand) so nothing fetches until the approver opens it.
 *
 * Note: the bank org-hierarchy (manager→reports) is not modelled, so this is the employee's OWN
 * history; a subordinate rollup would need an org-chart data source we don't have.
 */
import { useQuery } from '@tanstack/react-query'
import { Activity, Gauge, Moon, ScrollText } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { formatRelative, humanize, featureFriendlyLabel } from '@/lib/format'
import { riskColor } from '@/lib/risk'
import type { AuditEvent } from '@/lib/types'

/** Friendly names for the dotted audit vocabulary; unknown actions fall back to humanize(). */
const AUDIT_ACTION_LABEL: Record<string, string> = {
  'alert.view': 'viewed the alert',
  'alert.disposition': 'dispositioned the alert',
  'alert.assign': 'assigned the alert',
  'alert.block_request': 'requested a block',
  'alert.block_approved': 'approved a block',
  'pii.unmask': 'unmasked PII',
  'entity.view': 'opened the profile',
  'entity.timeline': 'viewed the timeline',
  'narrative.generate': 'generated the AI memo',
  'action_gate.decision': 'decided a held action',
}

function auditActionLabel(action: string): string {
  return AUDIT_ACTION_LABEL[action] ?? humanize(action.replace(/\./g, ' '))
}

/** Pull a short human note out of the free-form audit detail (object or string), defensively. */
function auditNote(ev: AuditEvent): string {
  const d = ev.detail
  if (d && typeof d === 'object') {
    if (typeof d.outcome === 'string') return d.outcome.replace(/_/g, ' ')
    if (typeof d.alert_id === 'string') return d.alert_id
  }
  if (typeof d === 'string') return d
  return ev.outcome ? String(ev.outcome).replace(/_/g, ' ') : ''
}

interface Timelineish {
  ts?: string
  verb?: string
  is_off_hours?: boolean
  action?: { verb?: string }
  context?: { is_off_hours?: boolean }
}
function evVerb(e: Timelineish): string {
  return e.action?.verb ?? e.verb ?? '—'
}
function evOffHours(e: Timelineish): boolean {
  return Boolean(e.context?.is_off_hours ?? e.is_off_hours)
}

export function EmployeeActivitySummary({
  entityId,
  enabled = true,
  className,
}: {
  entityId: string
  enabled?: boolean
  className?: string
}) {
  const risk = useQuery({
    queryKey: queryKeys.riskIndex(entityId),
    queryFn: () => apiClient.getRiskIndex(entityId),
    enabled,
    staleTime: 60_000,
  })
  const timeline = useQuery({
    queryKey: queryKeys.entityTimeline(entityId),
    queryFn: () => apiClient.getEntityTimeline(entityId),
    enabled,
    staleTime: 60_000,
  })
  const audit = useQuery({
    queryKey: queryKeys.audit({ entity: entityId, page_size: 8 }),
    queryFn: () => apiClient.getAudit({ entity: entityId, page_size: 8 }),
    enabled,
    staleTime: 60_000,
    retry: false, // a role without VIEW_AUDIT 403s — hide the block rather than retry
  })

  const events = ((timeline.data?.events ?? []) as Timelineish[]).slice(0, 5)
  const auditItems = (audit.data?.items ?? []).slice(0, 6)
  const loading = risk.isLoading || timeline.isLoading

  return (
    <div className={cn('space-y-3 rounded-md bg-muted/30 p-3 text-xs', className)}>
      {/* Insider-risk index */}
      {risk.data ? (
        <div className="flex items-start gap-2">
          <Gauge className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <span className="font-medium text-foreground">Insider-risk index </span>
            <span
              className="font-mono font-semibold tabular-nums"
              style={{ color: riskColor(risk.data.composite) }}
            >
              {risk.data.composite}/100
            </span>
            {risk.data.top_drivers?.length ? (
              <span className="text-muted-foreground">
                {' '}
                · drivers:{' '}
                {risk.data.top_drivers
                  .slice(0, 3)
                  .map((d) => featureFriendlyLabel(d))
                  .join(', ')}
              </span>
            ) : null}
            {risk.data.calibrated === false ? (
              <span className="ml-1 text-2xs text-muted-foreground/70">(indicative)</span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Recent operational activity (their own actions) */}
      {events.length > 0 ? (
        <div>
          <p className="mb-1 flex items-center gap-1.5 font-medium uppercase tracking-wide text-muted-foreground">
            <Activity className="size-3" /> Recent activity
          </p>
          <ol className="space-y-0.5 border-l border-border/50 pl-3">
            {events.map((e, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate">
                  {humanize(evVerb(e))}
                  {evOffHours(e) ? (
                    <Moon
                      className="ml-1 inline size-3 text-severity-medium"
                      aria-label="off-hours"
                    />
                  ) : null}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground" title={e.ts}>
                  {e.ts ? formatRelative(e.ts) : ''}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {/* Decision log — who has acted on this entity in the system (audit trail) */}
      {auditItems.length > 0 ? (
        <div>
          <p className="mb-1 flex items-center gap-1.5 font-medium uppercase tracking-wide text-muted-foreground">
            <ScrollText className="size-3" /> Who has looked at this
          </p>
          <ol className="space-y-0.5 border-l border-border/50 pl-3">
            {auditItems.map((ev) => {
              const note = auditNote(ev)
              return (
                <li key={ev.audit_id} className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate">
                    <span className="font-medium text-foreground">
                      {humanize(String(ev.actor_role ?? ev.actor ?? 'user'))}
                    </span>{' '}
                    {auditActionLabel(ev.action)}
                    {note ? <span className="text-muted-foreground"> · {note}</span> : null}
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground" title={ev.ts}>
                    {formatRelative(ev.ts)}
                  </span>
                </li>
              )
            })}
          </ol>
        </div>
      ) : null}

      {loading ? <p className="text-muted-foreground">Loading history…</p> : null}
      {!loading && !risk.data && events.length === 0 && auditItems.length === 0 ? (
        <p className="text-muted-foreground">No prior activity on record for this entity.</p>
      ) : null}
    </div>
  )
}
