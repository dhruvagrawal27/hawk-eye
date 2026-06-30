/**
 * One row in the triage queue (FRONTEND-4). Presentational — the queue owns data, sort, dedup and
 * virtualization; this renders a single (possibly deduped) alert with the column grid the header in
 * TriageQueue declares. Severity-bar gutter, fused composite, colour-graded SLA, and a one-click
 * CLAIM gated on `triage` (golden rule #2). Money is INR, ids are tokenized PII (golden rule #3/#5).
 */
import { ChevronRight, Layers, UserPlus2, Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'
import { compositePriority, formatINRCompact, formatNumber, humanize } from '@/lib/format'
import type { Alert, Severity } from '@/lib/types'
import { MaskedPII } from '@/components/MaskedPII'
import { SlaTimer } from '@/components/SlaTimer'
import { ConfidenceMeter, ContributingLayers, RiskScore, SeverityBadge } from '@/components/badges'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/**
 * Layout grid shared by the row and the header in TriageQueue — keep the two in lock-step.
 * Leading 2.25rem column is the bulk-select checkbox.
 */
export const ALERT_ROW_GRID =
  'grid grid-cols-[2.25rem_3.25rem_5.5rem_minmax(8rem,1fr)_minmax(11rem,1.4fr)_6.5rem_6.5rem_5.5rem_9rem_8rem_6rem] items-center gap-2'

const severityGutter: Record<Severity, string> = {
  critical: 'bg-severity-critical motion-safe:animate-pulse-urgent',
  high: 'bg-severity-high',
  medium: 'bg-severity-medium',
  low: 'bg-severity-low',
}

// Faint full-row tint so a critical alert never looks like a low one (study S3).
const severityRowTint: Record<Severity, string> = {
  critical: 'bg-severity-critical/[0.06]',
  high: 'bg-severity-high/[0.04]',
  medium: '',
  low: '',
}

export function AlertRow({
  alert,
  duplicateCount = 0,
  canClaim = false,
  claiming = false,
  selected = false,
  selectable = false,
  onSelectChange,
  onOpen,
  onClaim,
  now,
}: {
  alert: Alert
  /** Number of *additional* alerts collapsed under this entity row (0 when not deduped). */
  duplicateCount?: number
  canClaim?: boolean
  claiming?: boolean
  selected?: boolean
  /** When true the leading checkbox is interactive (bulk-select enabled for this role). */
  selectable?: boolean
  /** Fired when the row's checkbox toggles — `next` is the desired selected state. */
  onSelectChange?: (alert: Alert, next: boolean) => void
  onOpen: (alert: Alert) => void
  onClaim?: (alert: Alert) => void
  now?: Date
}) {
  const composite = compositePriority(alert)
  const title = alert.title ?? humanize(alert.alert_type ?? 'Suspicious activity')
  const type = alert.alert_type ? humanize(alert.alert_type) : null

  return (
    <div
      role="row"
      tabIndex={0}
      aria-selected={selected}
      data-alert-id={alert.alert_id}
      onClick={() => onOpen(alert)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen(alert)
        }
      }}
      className={cn(
        'group relative cursor-pointer border-b border-border/70 pl-3 pr-2 transition-colors hover:bg-muted/40 focus-ring',
        severityRowTint[alert.severity],
        selected && 'bg-muted/60',
      )}
    >
      {/* severity gutter */}
      <span
        aria-hidden
        className={cn('absolute inset-y-0 left-0 w-1', severityGutter[alert.severity])}
      />

      <div className={cn(ALERT_ROW_GRID, 'py-[var(--row-py)]')}>
        {/* bulk-select checkbox — clicks here must not open the alert */}
        <div role="cell" className="flex justify-center" onClick={(e) => e.stopPropagation()}>
          {selectable ? (
            <Checkbox
              checked={selected}
              onCheckedChange={(v) => onSelectChange?.(alert, v === true)}
              aria-label={`Select ${alert.alert_id}`}
            />
          ) : null}
        </div>

        {/* risk */}
        <div role="cell" className="flex justify-center">
          <RiskScore score={alert.risk_score} size="sm" />
        </div>

        {/* severity + composite */}
        <div role="cell" className="flex flex-col items-start gap-1">
          <SeverityBadge severity={alert.severity} />
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-[0.7rem] tabular-nums text-muted-foreground">
                P {formatNumber(composite, 0)}
              </span>
            </TooltipTrigger>
            <TooltipContent>
              Fused composite priority = risk × exposure × confidence (Part 11). Higher = triage
              sooner.
            </TooltipContent>
          </Tooltip>
        </div>

        {/* entity (tokenized PII) */}
        <div role="cell" className="min-w-0 truncate text-sm">
          <MaskedPII value={alert.entity_id} entityId={alert.entity_id} alertId={alert.alert_id} />
        </div>

        {/* title / type */}
        <div role="cell" className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-sm font-medium" title={title}>
              {title}
            </p>
            {duplicateCount > 0 ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="secondary" className="shrink-0 tabular-nums">
                    +{duplicateCount} more
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>
                  {duplicateCount + 1} open alerts for this entity — showing the highest-risk
                  representative.
                </TooltipContent>
              </Tooltip>
            ) : null}
          </div>
          {type ? (
            <p className="truncate text-xs text-muted-foreground" title={type}>
              {type} · <span className="font-mono">{alert.alert_id}</span>
            </p>
          ) : (
            <p className="truncate font-mono text-xs text-muted-foreground">{alert.alert_id}</p>
          )}
        </div>

        {/* exposure (INR) */}
        <div role="cell" className="text-right text-sm font-medium tabular-nums">
          {formatINRCompact(alert.exposure_inr)}
        </div>

        {/* confidence */}
        <div role="cell">
          <ConfidenceMeter confidence={alert.confidence} />
        </div>

        {/* contributing layers */}
        <div role="cell" className="min-w-0">
          {alert.contributing_layers.length ? (
            <ContributingLayers layers={alert.contributing_layers} />
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Layers className="size-3" /> —
            </span>
          )}
        </div>

        {/* SLA */}
        <div role="cell">
          <SlaTimer dueTs={alert.sla_due_ts} compact now={now} />
        </div>

        {/* assignee */}
        <div role="cell" className="min-w-0 truncate text-xs">
          {alert.assignee ? (
            <span className="font-medium text-foreground" title={alert.assignee}>
              {alert.assignee}
            </span>
          ) : (
            <span className="text-muted-foreground">Unassigned</span>
          )}
        </div>

        {/* claim / open */}
        <div role="cell" className="flex items-center justify-end gap-1">
          {canClaim && onClaim ? (
            <Button
              size="sm"
              variant={alert.assignee ? 'ghost' : 'secondary'}
              className="h-7 px-2"
              disabled={claiming}
              onClick={(e) => {
                e.stopPropagation()
                onClaim(alert)
              }}
              aria-label={`Claim ${alert.alert_id}`}
            >
              {claiming ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <UserPlus2 className="size-3.5" />
              )}
              <span className="text-xs">{alert.assignee ? 'Reassign' : 'Claim'}</span>
            </Button>
          ) : null}
          <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </div>
      </div>
    </div>
  )
}
