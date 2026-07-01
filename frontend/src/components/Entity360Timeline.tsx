/**
 * Entity-360 unified timeline (FRONTEND-7; blueprint Part 11 l.388 + Part 24.4 l.950 + Part 24.5a).
 *
 * ONE ordered timeline that merges the four L0 event families (transactions, access, data-layer,
 * HR/change) derived from `context.layer` / `action.channel`. Above it sits a compact profile header
 * (role · dept · branch · peer group · tenure · risk · actor flags) from `getEntity`, a legend
 * mapping families → colour, a per-family toggle filter, and a newest/oldest ordering switch. The
 * long history scrolls inside a <ScrollArea>; clicking a row expands its full detail.
 *
 * Every panel degrades the same way: <QueryBoundary> for loading/error, <EmptyState> for empty.
 */
import { useMemo, useState } from 'react'
import {
  ArrowDownWideNarrow,
  ArrowUpWideNarrow,
  Building2,
  CalendarClock,
  History,
  Users,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatNumber, humanize } from '@/lib/format'
import { useQuery } from '@tanstack/react-query'
import { MaskedPII } from '@/components/MaskedPII'
import { RiskScore, PrivilegedFlag, LeaverFlag, PiiTokenizedBadge } from '@/components/badges'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import {
  TimelineEvent,
  FAMILY_META,
  FAMILY_ORDER,
  familyForEvent,
} from '@/components/TimelineEvent'
import { ActivityHeatmap, type ActivityPoint } from '@/components/ActivityHeatmap'
import { LayerScoreTimeline } from '@/components/LayerScoreTimeline'
import type { EntityProfile, EventFamily, TimelineEntry } from '@/lib/types'

type FamilyFilter = Record<EventFamily, boolean>
const ALL_ON: FamilyFilter = { transaction: true, access: true, data: true, change: true }

/* ── Profile header derived from getEntity ────────────────────────────────────────────────────── */
function ProfileHeader({ entity, alertId }: { entity: EntityProfile; alertId?: string }) {
  const tenureYears = entity.tenure_days / 365
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-3 p-4">
        <div className="flex items-center gap-3">
          <RiskScore score={entity.risk_score} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <MaskedPII
                value={entity.display_name || entity.entity_id}
                entityId={entity.entity_id}
                alertId={alertId}
                className="text-sm font-semibold"
              />
              {entity.pii_tokenized ? <PiiTokenizedBadge /> : null}
            </div>
            <p className="text-xs text-muted-foreground">
              {humanize(entity.role)} · {humanize(entity.dept)}
            </p>
          </div>
        </div>

        <Separator orientation="vertical" className="hidden h-10 sm:block" />

        <dl className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <Stat icon={Building2} label="Branch" value={entity.branch} />
          <Stat icon={Users} label="Peer group" value={entity.peer_group} />
          <Stat
            icon={CalendarClock}
            label="Tenure"
            value={`${formatNumber(tenureYears, 1)} yr`}
            title={`${formatNumber(entity.tenure_days)} days`}
          />
          {entity.open_alert_count != null ? (
            <Stat
              icon={History}
              label="Open alerts"
              value={formatNumber(entity.open_alert_count)}
            />
          ) : null}
        </dl>

        {entity.privileged_flag || entity.leaver_flag ? (
          <div className="ml-auto flex items-center gap-3">
            {entity.privileged_flag ? <PrivilegedFlag /> : null}
            {entity.leaver_flag ? <LeaverFlag /> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function Stat({
  icon: Icon,
  label,
  value,
  title,
}: {
  icon: typeof Building2
  label: string
  value: string
  title?: string
}) {
  return (
    <div className="flex items-center gap-1.5" title={title}>
      <Icon className="size-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
      <dd className="font-medium tabular-nums text-foreground">{value}</dd>
    </div>
  )
}

/* ── Legend + per-family filter toggles ───────────────────────────────────────────────────────── */
function FamilyControls({
  filter,
  counts,
  onToggle,
}: {
  filter: FamilyFilter
  counts: Record<EventFamily, number>
  onToggle: (family: EventFamily) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {FAMILY_ORDER.map((family) => {
        const meta = FAMILY_META[family]
        const Icon = meta.icon
        const active = filter[family]
        const id = `family-${family}`
        return (
          <label
            key={family}
            htmlFor={id}
            className={cn(
              'flex cursor-pointer select-none items-center gap-2 rounded-md border px-2.5 py-1.5 text-xs transition-colors',
              active
                ? 'border-border bg-card'
                : 'border-dashed border-border bg-transparent opacity-60',
            )}
          >
            <Checkbox id={id} checked={active} onCheckedChange={() => onToggle(family)} />
            <span
              className={cn(
                'flex size-5 items-center justify-center rounded',
                meta.tint,
                meta.text,
              )}
            >
              <Icon className="size-3.5" />
            </span>
            <span className="font-medium text-foreground">{meta.label}</span>
            <span className="tabular-nums text-muted-foreground">{counts[family]}</span>
          </label>
        )
      })}
    </div>
  )
}

function TimelineSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-3 pl-7">
          <Skeleton className="h-16 w-full rounded-lg" />
        </div>
      ))}
    </div>
  )
}

export function Entity360Timeline({ entityId, alertId }: { entityId: string; alertId?: string }) {
  const [filter, setFilter] = useState<FamilyFilter>(ALL_ON)
  const [newestFirst, setNewestFirst] = useState(true)

  const entityQuery = useQuery({
    queryKey: queryKeys.entity(entityId),
    queryFn: () => apiClient.getEntity(entityId),
  })
  const timelineQuery = useQuery({
    queryKey: queryKeys.entityTimeline(entityId),
    queryFn: () => apiClient.getEntityTimeline(entityId),
  })

  const allEvents = useMemo(() => timelineQuery.data?.events ?? [], [timelineQuery.data])

  /** Points for the 7×24 activity heatmap (off-hours from the L0 context flag when present). */
  const activityPoints = useMemo<ActivityPoint[]>(
    () => allEvents.map((e) => ({ ts: e.ts, offHours: e.context?.is_off_hours })),
    [allEvents],
  )

  /** Per-family counts across the full history (drives the filter chips). */
  const counts = useMemo(() => {
    const c: Record<EventFamily, number> = { transaction: 0, access: 0, data: 0, change: 0 }
    for (const e of allEvents) c[familyForEvent(e)] += 1
    return c
  }, [allEvents])

  /** Filtered + ordered list. */
  const events = useMemo(() => {
    const list = allEvents.filter((e) => filter[familyForEvent(e)])
    list.sort((a, b) => {
      const ta = new Date(a.ts).getTime()
      const tb = new Date(b.ts).getTime()
      return newestFirst ? tb - ta : ta - tb
    })
    return list
  }, [allEvents, filter, newestFirst])

  function toggleFamily(family: EventFamily) {
    setFilter((f) => ({ ...f, [family]: !f[family] }))
  }

  function handleSelect(_e: TimelineEntry) {
    // expansion state is local to <TimelineEvent>; hook reserved for parent-driven detail panes
  }

  return (
    <section className="space-y-4" aria-label="Entity 360 unified timeline">
      <QueryBoundary
        isLoading={entityQuery.isLoading}
        isError={entityQuery.isError}
        error={entityQuery.error}
        onRetry={() => void entityQuery.refetch()}
        skeleton={<Skeleton className="h-20 w-full rounded-lg" />}
      >
        {entityQuery.data ? <ProfileHeader entity={entityQuery.data} alertId={alertId} /> : null}
      </QueryBoundary>

      {activityPoints.length > 0 ? <ActivityHeatmap points={activityPoints} /> : null}

      {/* Per-layer score timeline — which detection layer saw it first, decomposed over time. */}
      <LayerScoreTimeline entityId={entityId} />

      <Card>
        <CardHeader className="gap-3 pb-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2">
                <History className="size-4 text-muted-foreground" />
                Unified activity timeline
              </CardTitle>
              <p className="mt-1 text-xs text-muted-foreground">
                Transactions · access · data-layer · HR/change merged into one ordered history.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setNewestFirst((v) => !v)}
              title={newestFirst ? 'Showing newest first' : 'Showing oldest first'}
            >
              {newestFirst ? (
                <ArrowDownWideNarrow className="size-4" />
              ) : (
                <ArrowUpWideNarrow className="size-4" />
              )}
              {newestFirst ? 'Newest first' : 'Oldest first'}
            </Button>
          </div>
          <FamilyControls filter={filter} counts={counts} onToggle={toggleFamily} />
        </CardHeader>

        <CardContent>
          <QueryBoundary
            isLoading={timelineQuery.isLoading}
            isError={timelineQuery.isError}
            error={timelineQuery.error}
            onRetry={() => void timelineQuery.refetch()}
            skeleton={<TimelineSkeleton />}
          >
            {allEvents.length === 0 ? (
              <EmptyState
                icon={History}
                title="No activity recorded"
                description="No L0 events have been ingested for this entity yet."
              />
            ) : events.length === 0 ? (
              <EmptyState
                icon={History}
                title="No events match the active filters"
                description="Re-enable one or more event families above to see this entity's history."
                action={
                  <Button variant="outline" size="sm" onClick={() => setFilter(ALL_ON)}>
                    Show all families
                  </Button>
                }
              />
            ) : (
              <ScrollArea className="-mr-2 max-h-[34rem] pr-2">
                <ol className="relative space-y-3 border-l border-border/60 py-1">
                  {events.map((event) => (
                    <TimelineEvent key={event.event_id} event={event} onSelect={handleSelect} />
                  ))}
                </ol>
                <p className="px-7 pt-3 text-center text-[0.7rem] text-muted-foreground">
                  Showing {events.length} of {allEvents.length} events · all PII tokenized by
                  default
                </p>
              </ScrollArea>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>
    </section>
  )
}
