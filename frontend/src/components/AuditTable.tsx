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
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Eye, Gavel, ScrollText, ShieldOff } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIST, humanize } from '@/lib/format'
import { MaskedPII } from '@/components/MaskedPII'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/components/ui/empty-state'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { AuditEvent } from '@/lib/types'

// Live backend uses a dotted action vocabulary (alert.view / pii.unmask / alert.disposition …).
// Legacy underscore names are kept so MSW / older fixtures still classify correctly.
/** Actions that record who looked at a person — the privacy-sensitive reads. */
const VIEW_ACTIONS = new Set(['entity.view', 'alert.view', 'pii.unmask', 'view_entity', 'unmask_pii'])
/** Actions that record who decided a case — the accountability-critical writes. */
const DECISION_ACTIONS = new Set([
  'alert.disposition',
  'alert.block_request',
  'alert.block_approved',
  'model.promote',
  'rule.change_approved',
  'rule.change_proposed',
  'rule.change_rejected',
  // legacy
  'disposition',
  'close_alert',
  'close',
  'block_request',
  'promote_model',
])

const UNMASK_ACTIONS = new Set(['pii.unmask', 'unmask_pii'])

/**
 * Render the audit `detail` safely. The live backend sends it as an OBJECT (e.g.
 * `{alert_id, outcome, evidence_ids}`); a raw object as a React child throws
 * "Objects are not valid as a React child". Flatten to a compact `key: value` string.
 */
function formatDetail(detail: AuditEvent['detail']): string {
  if (detail == null) return ''
  if (typeof detail === 'string') return detail
  if (typeof detail !== 'object') return String(detail)
  try {
    const parts = Object.entries(detail)
      .filter(([, v]) => v != null && !(Array.isArray(v) && v.length === 0))
      .map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`)
    return parts.length > 0 ? parts.join(' · ') : ''
  } catch {
    return ''
  }
}

type ActionKind = 'view' | 'decision' | 'other'

function actionKind(action: string): ActionKind {
  if (VIEW_ACTIONS.has(action)) return 'view'
  if (DECISION_ACTIONS.has(action)) return 'decision'
  return 'other'
}

/** Plain-language meaning of an audit action, so a row is interpretable without insider knowledge. */
function explainAction(action: string): string {
  const a = action.replace(/\./g, '_')
  const HELP: Record<string, string> = {
    entity_view: 'A user opened an employee/entity profile — a privacy-sensitive read.',
    alert_view: 'A user opened an alert’s detail — a privacy-sensitive read.',
    view_entity: 'A user opened an employee/entity profile — a privacy-sensitive read.',
    pii_unmask: 'A user revealed masked personal data (name/account) — case-scoped and logged.',
    unmask_pii: 'A user revealed masked personal data (name/account) — case-scoped and logged.',
    alert_disposition: 'A user decided an alert (true / false positive) — an accountable write.',
    disposition: 'A user decided an alert (true / false positive) — an accountable write.',
    close_alert: 'A user closed an alert.',
    alert_block_request: 'A user requested an account/action block for review (alert-only — never auto-applied).',
    alert_block_approved: 'A supervisor approved a requested block.',
    model_promote: 'A model version was promoted to Production.',
    rule_change_proposed: 'A rule change was proposed (four-eyes change control).',
    rule_change_approved: 'A rule change was approved and took effect.',
    rule_change_rejected: 'A proposed rule change was rejected.',
  }
  if (HELP[a]) return HELP[a]
  const kind = actionKind(action)
  if (kind === 'view') return 'A privacy-sensitive read of case/entity data.'
  if (kind === 'decision') return 'An accountability-critical decision recorded in the trail.'
  return 'A recorded system/user action.'
}

function ActionCell({ action }: { action: string }) {
  const kind = actionKind(action)
  const isUnmask = UNMASK_ACTIONS.has(action)
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
      {humanize(action.replace(/\./g, ' '))}
    </span>
  )
}

function AuditRow({ ev, onSelect }: { ev: AuditEvent; onSelect: () => void }) {
  const kind = actionKind(ev.action)
  const detailObj =
    ev.detail && typeof ev.detail === 'object' ? (ev.detail as Record<string, unknown>) : undefined
  // The live backend nests alert_id / outcome inside `detail`; fall back to those when the
  // top-level fields are absent (older shapes carried them at the top level).
  const alertId =
    ev.alert_id ?? (typeof detailObj?.alert_id === 'string' ? detailObj.alert_id : undefined)
  const outcome =
    ev.outcome ?? (typeof detailObj?.outcome === 'string' ? detailObj.outcome : undefined)
  const detailText = formatDetail(ev.detail)
  return (
    <TableRow
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect()
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`Inspect audit event: ${humanize(ev.action.replace(/\./g, ' '))} by ${ev.actor}`}
      className={cn(
        'cursor-pointer focus-ring',
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
      <TableCell onClick={(e) => e.stopPropagation()}>
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
        {alertId ? (
          <span className="text-muted-foreground">{alertId}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        {outcome ? (
          <Badge variant="outline" className="font-normal">
            {humanize(outcome)}
          </Badge>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="max-w-[18rem]">
        {detailText ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="block truncate text-xs text-muted-foreground">{detailText}</span>
            </TooltipTrigger>
            <TooltipContent>
              <span className="block max-w-[24rem] whitespace-pre-wrap break-words">
                {detailText}
              </span>
            </TooltipContent>
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
  const [selected, setSelected] = useState<AuditEvent | null>(null)

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
    <>
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
            <AuditRow key={ev.audit_id} ev={ev} onSelect={() => setSelected(ev)} />
          ))}
        </TableBody>
      </Table>
      <AuditDetailDialog event={selected} onClose={() => setSelected(null)} />
    </>
  )
}

/* ── Row drill-down: the full, interpretable record for one audit event ─────── */
function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr] gap-2 py-1 text-sm">
      <span className="text-xs uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words">{children}</span>
    </div>
  )
}

function AuditDetailDialog({ event, onClose }: { event: AuditEvent | null; onClose: () => void }) {
  const ev = event
  const detailObj =
    ev?.detail && typeof ev.detail === 'object' ? (ev.detail as Record<string, unknown>) : undefined
  const alertId =
    ev?.alert_id ?? (typeof detailObj?.alert_id === 'string' ? detailObj.alert_id : undefined)
  const outcome =
    ev?.outcome ?? (typeof detailObj?.outcome === 'string' ? detailObj.outcome : undefined)
  const detailPretty =
    ev?.detail == null
      ? ''
      : typeof ev.detail === 'object'
        ? JSON.stringify(ev.detail, null, 2)
        : String(ev.detail)

  return (
    <Dialog open={ev !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        {ev ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ActionCell action={ev.action} />
              </DialogTitle>
              <DialogDescription>{explainAction(ev.action)}</DialogDescription>
            </DialogHeader>

            <div className="divide-y divide-border/60">
              <DetailRow label="When">
                <span className="tabular-nums">{formatIST(ev.ts)}</span>
              </DetailRow>
              <DetailRow label="Actor">
                <span className="font-medium">{ev.actor}</span>
                {ev.actor_role ? (
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    ({humanize(ev.actor_role)})
                  </span>
                ) : null}
              </DetailRow>
              <DetailRow label="Subject">
                {ev.entity_id ? (
                  <MaskedPII value={ev.entity_id} entityId={ev.entity_id} alertId={alertId} />
                ) : ev.target ? (
                  <span className="font-mono text-xs">{ev.target}</span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </DetailRow>
              {alertId ? (
                <DetailRow label="Alert">
                  <Link
                    to={`/alerts/${alertId}`}
                    onClick={onClose}
                    className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline"
                  >
                    {alertId}
                    <ArrowUpRight className="size-3" />
                  </Link>
                </DetailRow>
              ) : null}
              {outcome ? (
                <DetailRow label="Outcome">
                  <Badge variant="outline" className="font-normal">
                    {humanize(outcome)}
                  </Badge>
                </DetailRow>
              ) : null}
              <DetailRow label="Source IP">
                <span className="font-mono text-xs">{ev.src_ip ?? '—'}</span>
              </DetailRow>
              <DetailRow label="Event ID">
                <span className="font-mono text-xs text-muted-foreground">{ev.audit_id}</span>
              </DetailRow>
            </div>

            {detailPretty ? (
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-muted-foreground">
                  Full detail (as recorded)
                </p>
                <pre className="max-h-56 overflow-auto rounded-md bg-muted/60 p-2.5 text-[0.7rem] leading-relaxed">
                  {detailPretty}
                </pre>
              </div>
            ) : null}

            <p className="text-[0.7rem] text-muted-foreground">
              Immutable WORM record — shown for inspection only; audit entries can never be edited or
              deleted.
            </p>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" size="sm">
                  Close
                </Button>
              </DialogClose>
            </DialogFooter>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
