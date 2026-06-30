/**
 * One row in the Entity-360 unified timeline (FRONTEND-7; blueprint Part 11 l.388 + Part 24.4 l.950).
 *
 * Renders a single L0 `UnifiedEvent` grouped into actor / action / object / context, colour- and
 * icon-coded by its derived event family (transaction · access · data · change). Verbs are
 * humanized, amounts are INR, tokenized ids go through <MaskedPII>, and the off-hours / privileged /
 * leaver flags surface as the shared badges. Clicking the row toggles an expanded detail block and
 * notifies the parent via `onSelect`.
 */
import { useState } from 'react'
import {
  ArrowLeftRight,
  ChevronDown,
  Database,
  Fingerprint,
  Globe,
  Hash,
  Landmark,
  MonitorSmartphone,
  UserCog,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatINR, formatISTTime, formatISTDate, humanize } from '@/lib/format'
import { MaskedPII } from '@/components/MaskedPII'
import { OffHoursFlag, PrivilegedFlag, LeaverFlag } from '@/components/badges'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import type { EventFamily, TimelineEntry } from '@/lib/types'

/* ── Family → derivation, colour, icon, label (shared with the parent legend) ─────────────────── */

export interface FamilyMeta {
  family: EventFamily
  label: string
  icon: LucideIcon
  /** Tailwind text colour token. */
  text: string
  /** Tailwind background tint. */
  tint: string
  /** Tailwind ring/border tint for the rail dot. */
  ring: string
  /** Tailwind left-rail border colour. */
  rail: string
}

/**
 * The 4 event families derived from `context.layer` (primary) and `action.channel` (fallback).
 * Order matters: it is the legend/filter order.
 */
export const FAMILY_META: Record<EventFamily, FamilyMeta> = {
  transaction: {
    family: 'transaction',
    label: 'Transactions',
    icon: Landmark,
    text: 'text-severity-high',
    tint: 'bg-severity-high/12',
    ring: 'ring-severity-high/40',
    rail: 'border-severity-high/50',
  },
  access: {
    family: 'access',
    label: 'Access / Identity',
    icon: Fingerprint,
    text: 'text-reason-shap',
    tint: 'bg-reason-shap/12',
    ring: 'ring-reason-shap/40',
    rail: 'border-reason-shap/50',
  },
  data: {
    family: 'data',
    label: 'Data layer',
    icon: Database,
    text: 'text-reason-graph',
    tint: 'bg-reason-graph/12',
    ring: 'ring-reason-graph/40',
    rail: 'border-reason-graph/50',
  },
  change: {
    family: 'change',
    label: 'HR / Change',
    icon: UserCog,
    text: 'text-reason-rule',
    tint: 'bg-reason-rule/12',
    ring: 'ring-reason-rule/40',
    rail: 'border-reason-rule/50',
  },
}

export const FAMILY_ORDER: EventFamily[] = ['transaction', 'access', 'data', 'change']

/** Map an L0 event to one of the four families from `context.layer`, falling back to `action.channel`. */
export function familyForEvent(event: TimelineEntry): EventFamily {
  if (event.family) return event.family
  const layer = String(event.context.layer ?? '').toLowerCase()
  if (layer === 'application') return 'transaction'
  if (layer === 'identity') return 'access'
  if (layer === 'data') return 'data'
  if (layer === 'change') return 'change'

  const channel = String(event.action.channel ?? '').toLowerCase()
  if (channel === 'cbs') return 'transaction'
  if (channel === 'iam') return 'access'
  if (channel === 'db_audit') return 'data'
  if (channel === 'hr_iga') return 'change'

  return 'transaction'
}

/* ── A labelled key/value pair used in the actor/object/context groups ────────────────────────── */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className="text-xs text-foreground">{children}</span>
    </div>
  )
}

export function TimelineEvent({
  event,
  onSelect,
}: {
  event: TimelineEntry
  onSelect?: (e: TimelineEntry) => void
}) {
  const [open, setOpen] = useState(false)
  const family = familyForEvent(event)
  const meta = FAMILY_META[family]
  const Icon = meta.icon

  const { actor, action, object, context } = event
  const hasAmount = object.amount != null
  const hasFlags = context.is_off_hours || actor.privileged_flag || actor.leaver_flag

  function toggle() {
    setOpen((v) => !v)
    onSelect?.(event)
  }

  return (
    <li className="relative pl-7">
      {/* Rail dot */}
      <span
        className={cn(
          'absolute left-1.5 top-3 z-10 flex size-3 items-center justify-center rounded-full ring-4 ring-background',
          meta.tint,
        )}
        aria-hidden
      >
        <span className={cn('size-1.5 rounded-full bg-current', meta.text)} />
      </span>

      <div
        className={cn(
          'rounded-lg border border-l-2 border-border bg-card transition-colors hover:border-foreground/20',
          meta.rail,
        )}
      >
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="focus-ring flex w-full items-start gap-3 rounded-lg p-3 text-left"
        >
          <span
            className={cn(
              'mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md ring-1 ring-inset',
              meta.tint,
              meta.text,
              meta.ring,
            )}
          >
            <Icon className="size-4" />
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <span className="text-sm font-semibold text-foreground">{humanize(action.verb)}</span>
              <Badge variant="outline" className={cn('px-1.5 py-0 text-[0.65rem]', meta.text)}>
                {meta.label}
              </Badge>
              {action.maker_checker ? (
                <Badge variant="secondary" className="px-1.5 py-0 text-[0.65rem] uppercase">
                  {action.maker_checker}
                </Badge>
              ) : null}
              <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
                {formatISTTime(event.ts)}
              </span>
            </div>

            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <span className="text-muted-foreground/70">by</span>
                {/* Non-interactive in the collapsed toggle (no nested button); audited unmask lives
                    in the expanded detail below. */}
                <MaskedPII value={actor.employee_id} iconOnly />
              </span>
              {object.account_id ? (
                <span className="inline-flex items-center gap-1">
                  <span className="text-muted-foreground/70">acct</span>
                  <MaskedPII value={object.account_id} iconOnly />
                </span>
              ) : null}
              {object.beneficiary_id ? (
                <span className="inline-flex items-center gap-1">
                  <span className="text-muted-foreground/70">to</span>
                  <MaskedPII value={object.beneficiary_id} iconOnly />
                </span>
              ) : null}
              {hasAmount ? (
                <span className="font-medium tabular-nums text-foreground">
                  {formatINR(object.amount)}
                </span>
              ) : null}
              <span className="inline-flex items-center gap-1">
                <ArrowLeftRight className="size-3" />
                {humanize(action.channel)}
              </span>
            </div>

            {hasFlags ? (
              <div className="mt-1.5 flex flex-wrap items-center gap-3">
                {context.is_off_hours ? <OffHoursFlag /> : null}
                {actor.privileged_flag ? <PrivilegedFlag /> : null}
                {actor.leaver_flag ? <LeaverFlag /> : null}
              </div>
            ) : null}
          </div>

          <ChevronDown
            className={cn(
              'mt-1 size-4 shrink-0 text-muted-foreground transition-transform',
              open && 'rotate-180',
            )}
            aria-hidden
          />
        </button>

        {open ? (
          <div className="space-y-3 px-3 pb-3">
            <Separator />
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
              {/* Actor */}
              <Field label="Actor">
                <MaskedPII value={actor.employee_id} entityId={actor.employee_id} />
              </Field>
              <Field label="Role · Dept">
                {humanize(actor.role)} · {humanize(actor.dept)}
              </Field>
              <Field label="Branch">{actor.branch}</Field>
              <Field label="Peer group">{actor.peer_group}</Field>

              {/* Action */}
              <Field label="Action">{humanize(action.verb)}</Field>
              <Field label="Channel">{humanize(action.channel)}</Field>
              <Field label="Maker / checker">
                {action.maker_checker ? humanize(action.maker_checker) : '—'}
              </Field>
              <Field label="Layer">{humanize(String(context.layer))}</Field>

              {/* Object */}
              <Field label="Amount">{hasAmount ? formatINR(object.amount) : '—'}</Field>
              <Field label="Account">
                {object.account_id ? <MaskedPII value={object.account_id} /> : '—'}
              </Field>
              <Field label="Beneficiary">
                {object.beneficiary_id ? <MaskedPII value={object.beneficiary_id} /> : '—'}
              </Field>
              <Field label="Currency">{object.currency || '—'}</Field>
            </div>

            <Separator />

            {/* Context */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
              <Field label="When">
                <span className="inline-flex items-center gap-1">
                  {formatISTDate(event.ts)} · {formatISTTime(event.ts)}
                </span>
              </Field>
              <Field label="Source IP">
                <span className="inline-flex items-center gap-1 font-mono">
                  <Globe className="size-3 text-muted-foreground" />
                  {context.src_ip}
                </span>
              </Field>
              <Field label="Device">
                <span className="inline-flex items-center gap-1">
                  <MonitorSmartphone className="size-3 text-muted-foreground" />
                  {context.device}
                </span>
              </Field>
              <Field label="Geo">{context.geo}</Field>
              <Field label="Session">
                <span className="inline-flex items-center gap-1 font-mono text-[0.7rem]">
                  <Hash className="size-3 text-muted-foreground" />
                  {context.session_id}
                </span>
              </Field>
              <Field label="Event id">
                <span className="font-mono text-[0.7rem]">{event.event_id}</span>
              </Field>
            </div>
          </div>
        ) : null}
      </div>
    </li>
  )
}
