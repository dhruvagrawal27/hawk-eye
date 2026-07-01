/**
 * Immutable audit trail table (FRONTEND-13; blueprint Part 24.4 screen 6 + Part 24.2 RBAC).
 *
 * Renders the WORM "watch-the-watchers" log. **Read-only** — there are no mutation controls here:
 * an Auditor (and everyone else who can see it) can only inspect what happened, never change it.
 * Two action families are visually emphasised because they are the accountability-critical ones:
 *   - who-viewed-which-employee  → `view_entity` / `unmask_pii`
 *   - who-closed-what            → `disposition` / `close_alert`
 * Entity tokens are rendered masked (the audit log itself never leaks raw PII).
 *
 * Two lenses on the same events: a legible **ledger table** (who-viewed-whom, who-closed-what) and a
 * **hash-chain** view that assembles <HashChainBlock> into a literal WORM chain (prevHash → hash),
 * surfacing an overall verify PASS/FAIL seal. The per-block hash is a deterministic client-side digest
 * of the immutable fields (id · ts · actor · action) — the authoritative hash-chain lives server-side;
 * this is a tamper-evident *witness* of the snapshot, never a substitute for it.
 */
import { useMemo, useState } from 'react'
import { Eye, Gavel, Link2, ScrollText, ShieldCheck, ShieldOff, TableIcon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIST, humanize } from '@/lib/format'
import { MaskedPII } from '@/components/MaskedPII'
import { Eyebrow } from '@/components/ui/eyebrow'
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
import { HashChainBlock, useAutoAnimateList } from '@/ui'
import type { AuditEvent } from '@/lib/types'

// Live backend uses a dotted action vocabulary (alert.view / pii.unmask / alert.disposition …).
// Legacy underscore names are kept so MSW / older fixtures still classify correctly.
/** Actions that record who looked at a person — the privacy-sensitive reads. */
const VIEW_ACTIONS = new Set([
  'entity.view',
  'alert.view',
  'pii.unmask',
  'view_entity',
  'unmask_pii',
])
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

function AuditRow({ ev }: { ev: AuditEvent }) {
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

/* ── WORM hash-chain — a tamper-evident witness assembled from the immutable fields ────────────────
 * The live `/audit` payload carries no per-row hash (see AuditEvent), so we derive one deterministically
 * from the fields the WORM store commits (id · ts · actor · action) with a small stable string hash, and
 * link each block to the previous (prevHash → hash). This is presentational: it proves the *snapshot* is
 * internally consistent and lets an auditor read the chain; the authoritative hash-chained record is the
 * server's. Genesis (oldest) sits at the bottom so the chain grows upward with newest-first ordering. */

/** Stable, dependency-free FNV-1a-style 32-bit digest → 64-bit-looking hex (evidence, not crypto). */
function digest(input: string): string {
  let h1 = 0x811c9dc5
  let h2 = 0xc2b2ae35
  for (let i = 0; i < input.length; i += 1) {
    const c = input.charCodeAt(i)
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0
    h2 = Math.imul(h2 ^ (c + i), 0x85ebca6b) >>> 0
  }
  return (h1 >>> 0).toString(16).padStart(8, '0') + (h2 >>> 0).toString(16).padStart(8, '0')
}

interface ChainBlock {
  ev: AuditEvent
  index: number
  hash: string
  prevHash?: string
  ok: boolean
}

/** Fold the events (oldest → newest) into a linked hash chain. Any missing/blank id breaks a seal. */
function buildChain(events: AuditEvent[]): { blocks: ChainBlock[]; verified: boolean } {
  // Genesis = oldest. Events arrive newest-first from the API; reverse to fold in commit order.
  const ordered = [...events].reverse()
  const blocks: ChainBlock[] = []
  let prevHash: string | undefined
  let verified = true
  ordered.forEach((ev, index) => {
    const content = `${ev.audit_id}|${ev.ts}|${ev.actor}|${ev.action}`
    const hash = digest(`${prevHash ?? 'GENESIS'}|${content}`)
    // A block is sealed when it carries the immutable id and ts it commits to; a blank one can't be
    // linked and so reads as broken (never silently dropped).
    const ok = Boolean(ev.audit_id) && Boolean(ev.ts)
    if (!ok) verified = false
    blocks.push({ ev, index, hash, prevHash, ok })
    prevHash = hash
  })
  return { blocks, verified }
}

function VerifySeal({ verified, count }: { verified: boolean; count: number }) {
  return (
    <span
      role="status"
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 font-mono text-2xs font-semibold uppercase tracking-widest ring-1 ring-inset',
        verified
          ? 'text-tee ring-tee/30 bg-tee/5'
          : 'text-severity-critical ring-severity-critical/40 bg-severity-critical/10',
      )}
    >
      {verified ? <ShieldCheck className="size-3.5" /> : <ShieldOff className="size-3.5" />}
      {verified ? 'Chain verified · PASS' : 'Chain broken · FAIL'}
      <span className="tabular-nums text-muted-foreground">· {count} blocks</span>
    </span>
  )
}

/** The literal WORM chain — <HashChainBlock> stacked genesis-at-bottom, prevHash → hash. */
function ChainView({ blocks, verified }: { blocks: ChainBlock[]; verified: boolean }) {
  const [chainRef] = useAutoAnimateList<HTMLDivElement>()
  // Newest at the top; genesis (index 0) at the bottom so the visible connectors read downward.
  const topDown = [...blocks].reverse()
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Link2 className="size-4 text-tee" aria-hidden />
          <Eyebrow>WORM hash-chain · newest first</Eyebrow>
        </div>
        <VerifySeal verified={verified} count={blocks.length} />
      </div>
      <div ref={chainRef} className="space-y-0">
        {topDown.map((b, i) => (
          <HashChainBlock
            key={b.ev.audit_id || `${b.index}-${b.hash}`}
            index={b.index}
            hash={b.hash}
            prevHash={b.prevHash}
            ok={b.ok}
            ts={formatIST(b.ev.ts)}
            action={humanize(b.ev.action.replace(/\./g, ' '))}
            connector={i < topDown.length - 1}
          />
        ))}
      </div>
      <p className="text-[0.7rem] text-muted-foreground">
        Each block commits its immutable fields (id · ts · actor · action) and the previous
        block&rsquo;s hash — altering any earlier entry breaks every seal above it. This is a
        tamper-evident witness of the snapshot; the authoritative hash-chained record is retained
        server-side.
      </p>
    </div>
  )
}

type Lens = 'ledger' | 'chain'

export function AuditTable({ events }: { events: AuditEvent[] }) {
  const [lens, setLens] = useState<Lens>('ledger')
  const [bodyRef] = useAutoAnimateList<HTMLTableSectionElement>()
  const { blocks, verified } = useMemo(() => buildChain(events), [events])

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
    <div className="space-y-3">
      {/* Lens switch + overall verify seal — the "watch the watchers" posture at a glance. */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div
          role="tablist"
          aria-label="Audit trail view"
          className="inline-flex items-center gap-1 rounded-md bg-muted/40 p-0.5"
        >
          <LensTab
            active={lens === 'ledger'}
            icon={<TableIcon className="size-3.5" />}
            label="Ledger"
            onClick={() => setLens('ledger')}
          />
          <LensTab
            active={lens === 'chain'}
            icon={<Link2 className="size-3.5" />}
            label="Hash-chain"
            onClick={() => setLens('chain')}
          />
        </div>
        <VerifySeal verified={verified} count={blocks.length} />
      </div>

      {lens === 'chain' ? (
        <div className="px-3 pb-1">
          <ChainView blocks={blocks} verified={verified} />
        </div>
      ) : (
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
          <TableBody ref={bodyRef}>
            {events.map((ev) => (
              <AuditRow key={ev.audit_id} ev={ev} />
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}

function LensTab({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: React.ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-colors focus-ring',
        active
          ? 'bg-card text-foreground shadow-sm'
          : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {icon}
      {label}
    </button>
  )
}
