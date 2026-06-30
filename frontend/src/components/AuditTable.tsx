/**
 * Immutable audit trail table (FRONTEND-13; blueprint Part 24.4 screen 6 + Part 24.2 RBAC).
 *
 * Renders the WORM "watch-the-watchers" log. **Read-only** — there are no mutation controls here:
 * an Auditor (and everyone else who can see it) can only inspect what happened, never change it.
 * Two action families are visually emphasised because they are the accountability-critical ones:
 *   - who-viewed-which-employee  → `view_entity` / `unmask_pii`
 *   - who-closed-what            → `disposition` / `close_alert`
 * Entity tokens are rendered masked (the audit log itself never leaks raw PII).
 */
import { Eye, Gavel, ScrollText, ShieldOff } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIST, humanize } from '@/lib/format'
import { MaskedPII } from '@/components/MaskedPII'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/empty-state'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { AuditEvent } from '@/lib/types'

/** Actions that record who looked at a person — the privacy-sensitive reads. */
const VIEW_ACTIONS = new Set(['view_entity', 'unmask_pii'])
/** Actions that record who decided a case — the accountability-critical writes. */
const DECISION_ACTIONS = new Set([
  'disposition',
  'close_alert',
  'close',
  'block_request',
  'promote_model',
])

type ActionKind = 'view' | 'decision' | 'other'

function actionKind(action: string): ActionKind {
  if (VIEW_ACTIONS.has(action)) return 'view'
  if (DECISION_ACTIONS.has(action)) return 'decision'
  return 'other'
}

function ActionCell({ action }: { action: string }) {
  const kind = actionKind(action)
  const isUnmask = action === 'unmask_pii'
  const Icon = isUnmask
    ? ShieldOff
    : kind === 'view'
      ? Eye
      : kind === 'decision'
        ? Gavel
        : ScrollText
  const tone =
    kind === 'view'
      ? isUnmask
        ? 'text-severity-high'
        : 'text-reason-shap'
      : kind === 'decision'
        ? 'text-severity-medium'
        : 'text-muted-foreground'
  return (
    <span className={cn('inline-flex items-center gap-1.5 font-medium', tone)}>
      <Icon className="size-3.5 shrink-0" />
      {humanize(action)}
    </span>
  )
}

function AuditRow({ ev }: { ev: AuditEvent }) {
  const kind = actionKind(ev.action)
  return (
    <TableRow
      className={cn(
        kind === 'view' && 'bg-reason-shap/[0.04]',
        kind === 'decision' && 'bg-severity-medium/[0.04]',
      )}
    >
      <TableCell className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
        {formatIST(ev.ts)}
      </TableCell>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{ev.actor}</span>
          {ev.actor_role ? (
            <span className="text-[0.7rem] text-muted-foreground">{humanize(ev.actor_role)}</span>
          ) : null}
        </div>
      </TableCell>
      <TableCell>
        <ActionCell action={ev.action} />
      </TableCell>
      <TableCell>
        {ev.entity_id ? (
          <MaskedPII
            value={ev.entity_id}
            entityId={ev.entity_id}
            alertId={ev.alert_id ?? undefined}
          />
        ) : ev.target ? (
          <span className="font-mono text-xs text-muted-foreground">{ev.target}</span>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="font-mono text-xs">
        {ev.alert_id ? (
          <span className="text-muted-foreground">{ev.alert_id}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {ev.outcome ? (
          <Badge variant="outline" className="font-normal">
            {humanize(ev.outcome)}
          </Badge>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="max-w-[18rem]">
        {ev.detail ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="block truncate text-xs text-muted-foreground">{ev.detail}</span>
            </TooltipTrigger>
            <TooltipContent>{ev.detail}</TooltipContent>
          </Tooltip>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="whitespace-nowrap font-mono text-[0.7rem] text-muted-foreground">
        {ev.src_ip ?? '—'}
      </TableCell>
    </TableRow>
  )
}

export function AuditTable({ events }: { events: AuditEvent[] }) {
  if (events.length === 0) {
    return (
      <EmptyState
        icon={ScrollText}
        title="No audit events match"
        description="Adjust the actor, entity, action, or date filters to widen the immutable trail."
      />
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="min-w-[11rem]">Timestamp (IST)</TableHead>
          <TableHead>Actor</TableHead>
          <TableHead>Action</TableHead>
          <TableHead>Subject / target</TableHead>
          <TableHead>Alert</TableHead>
          <TableHead>Outcome</TableHead>
          <TableHead>Detail</TableHead>
          <TableHead>Source IP</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {events.map((ev) => (
          <AuditRow key={ev.audit_id} ev={ev} />
        ))}
      </TableBody>
    </Table>
  )
}
