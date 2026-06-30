/**
 * FRONTEND-4 — Triage queue (Analyst home). Blueprint Part 11 (l.387) + Part 24.4 screen 2.
 *
 * A virtualized work-queue over `apiClient.listAlerts(query)`. Rows are ordered by the fused
 * **composite priority** (risk × exposure × confidence — `compositePriority`, Part 11); columns are
 * sortable by risk / exposure / confidence / SLA. Alerts are **deduped per entity** by default (one
 * row per entity_id showing the highest-risk representative + a "+N more" badge) with a toggle back
 * to "all alerts". Server filters (status / risk_gte / assignee / type) are wired into the query AND
 * refined client-side so typing feels instant. CLAIM is one click, gated on `triage`, and surfaces
 * the audit_id (golden rules #1 alert-only / #2 RBAC / #3 PII / #5 IST·INR / #6 loading-empty-error).
 */
import { useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { useVirtualizer } from '@tanstack/react-virtual'
import {
  ArrowDownNarrowWide,
  ArrowUpDown,
  ArrowUpNarrowWide,
  Filter,
  Inbox,
  ListChecks,
  RotateCw,
  Search,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { compositePriority, slaInfo, statusLabel } from '@/lib/format'
import type { Alert, AlertQuery, AlertStatus } from '@/lib/types'
import { useAuth } from '@/auth/rbac'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AlertRow, ALERT_ROW_GRID } from '@/components/AlertRow'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { toast } from '@/components/ui/toaster'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

/* ── sortable columns ─────────────────────────────────────────────────────── */
type SortKey = 'composite' | 'risk_score' | 'exposure_inr' | 'confidence' | 'sla'

/** A queue row: a representative alert plus the alerts collapsed under it when deduping per entity. */
interface QueueRow {
  alert: Alert
  group: Alert[]
}

const STATUS_OPTIONS: AlertStatus[] = [
  'open',
  'assigned',
  'in_progress',
  'escalated',
  'confirmed_fraud',
  'false_positive',
  'inconclusive',
  'closed',
]
const RISK_FLOORS = [0, 40, 65, 85] as const
const ALL = '__all__'
const ROW_HEIGHT = 60

const SORT_KEYS: SortKey[] = ['risk_score', 'composite', 'exposure_inr', 'confidence', 'sla']
const SORT_LABELS: Record<SortKey, string> = {
  risk_score: 'Risk',
  composite: 'Severity / P',
  exposure_inr: 'Exposure',
  confidence: 'Confidence',
  sla: 'SLA',
}

function sortValue(alert: Alert, key: SortKey): number {
  switch (key) {
    case 'risk_score':
      return alert.risk_score
    case 'exposure_inr':
      return alert.exposure_inr
    case 'confidence':
      return alert.confidence
    case 'sla':
      // soonest-due first when descending feels wrong — encode "urgency": smaller ms remaining = higher
      return -slaInfo(alert.sla_due_ts).msRemaining
    case 'composite':
    default:
      return compositePriority(alert)
  }
}

export function TriageQueue() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, can } = useAuth()
  const mayTriage = can('triage')

  /* server-bound filters → become the query key (refetch on change) */
  const [status, setStatus] = useState<AlertStatus | ''>('')
  const [riskGte, setRiskGte] = useState<number>(0)
  const [assignee, setAssignee] = useState('')
  const [type, setType] = useState('')
  /* client-only refinements */
  const [search, setSearch] = useState('')
  const [dedupe, setDedupe] = useState(true)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({
    key: 'composite',
    dir: 'desc',
  })

  const query: AlertQuery = useMemo(
    () => ({
      status: status || undefined,
      risk_gte: riskGte || undefined,
      assignee: assignee.trim() || undefined,
      type: type.trim() || undefined,
      page_size: 1000,
    }),
    [status, riskGte, assignee, type],
  )

  const alertsQuery = useQuery({
    queryKey: queryKeys.alerts(query),
    queryFn: () => apiClient.listAlerts(query),
  })

  const claim = useMutation({
    mutationFn: (alertId: string) =>
      apiClient.assignAlert(alertId, { assignee: user?.username ?? 'me' }),
    onSuccess: (res) => {
      toast.success('Alert claimed', {
        description: `Assigned to ${res.assignee} · ${res.audit_id}`,
      })
      void queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
    onError: (err) =>
      toast.error('Claim failed', {
        description: err instanceof ApiError ? err.message : 'Could not assign this alert.',
      }),
  })

  const allAlerts = useMemo<Alert[]>(() => alertsQuery.data?.items ?? [], [alertsQuery.data])

  /* ── client refine: search across tokenized id / title / type / alert id ── */
  const refined = useMemo(() => {
    const needle = search.trim().toLowerCase()
    if (!needle) return allAlerts
    return allAlerts.filter((a) =>
      [a.entity_id, a.alert_id, a.title, a.alert_type, a.assignee]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle)),
    )
  }, [allAlerts, search])

  /* ── dedup per entity_id → one row per entity, highest-composite representative ── */
  const rows = useMemo<QueueRow[]>(() => {
    if (!dedupe) return refined.map((alert) => ({ alert, group: [alert] }))
    const byEntity = new Map<string, Alert[]>()
    for (const a of refined) {
      const list = byEntity.get(a.entity_id)
      if (list) list.push(a)
      else byEntity.set(a.entity_id, [a])
    }
    const grouped: QueueRow[] = []
    for (const group of byEntity.values()) {
      const rep = group.reduce((best, a) =>
        compositePriority(a) > compositePriority(best) ? a : best,
      )
      grouped.push({ alert: rep, group })
    }
    return grouped
  }, [refined, dedupe])

  /* ── react-table drives sort state (data already in memory; we virtualize rows) ── */
  const sorting: SortingState = [{ id: sort.key, desc: sort.dir === 'desc' }]
  const table = useReactTable<QueueRow>({
    data: rows,
    state: { sorting },
    columns: useMemo(
      () =>
        SORT_KEYS.map((key) => ({
          id: key,
          accessorFn: (row: QueueRow) => sortValue(row.alert, key),
        })),
      [],
    ),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableSortingRemoval: false,
  })

  const sortedRows = table.getRowModel().rows

  /* ── virtualization ───────────────────────────────────────────────────────── */
  const scrollRef = useRef<HTMLDivElement>(null)
  const virtualizer = useVirtualizer({
    count: sortedRows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  })
  const virtualItems = virtualizer.getVirtualItems()

  const total = alertsQuery.data?.total ?? allAlerts.length
  const collapsed = allAlerts.length - rows.length
  const filtersActive = Boolean(status || riskGte || assignee || type || search)

  function toggleSort(key: SortKey) {
    setSort((prev) =>
      prev.key === key ? { key, dir: prev.dir === 'desc' ? 'asc' : 'desc' } : { key, dir: 'desc' },
    )
  }

  function headerProps(key: SortKey) {
    return {
      label: SORT_LABELS[key],
      active: sort.key === key,
      dir: sort.dir,
      onClick: () => toggleSort(key),
    }
  }

  function resetFilters() {
    setStatus('')
    setRiskGte(0)
    setAssignee('')
    setType('')
    setSearch('')
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <PageHeader
        title="Triage queue"
        description="Open alerts ranked by fused risk × exposure × confidence. Claim to investigate — nothing auto-blocks or auto-closes."
        icon={<ListChecks className="size-5" />}
        actions={
          <div className="flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
              <Switch
                checked={dedupe}
                onCheckedChange={setDedupe}
                aria-label="Toggle deduplicate per entity"
              />
              <span>{dedupe ? 'Deduped per entity' : 'All alerts'}</span>
            </label>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void alertsQuery.refetch()}
              disabled={alertsQuery.isFetching}
            >
              <RotateCw className={cn('size-3.5', alertsQuery.isFetching && 'animate-spin')} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* ── filter bar ───────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card/40 p-3">
        <div className="relative min-w-[14rem] flex-1">
          <Label htmlFor="triage-search" className="mb-1 block text-xs text-muted-foreground">
            Search
          </Label>
          <Search className="pointer-events-none absolute left-2.5 top-[2.05rem] size-3.5 text-muted-foreground" />
          <Input
            id="triage-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Entity, alert id, title…"
            className="pl-8"
          />
        </div>

        <div className="w-40">
          <Label className="mb-1 block text-xs text-muted-foreground">Status</Label>
          <Select
            value={status || ALL}
            onValueChange={(v) => setStatus(v === ALL ? '' : (v as AlertStatus))}
          >
            <SelectTrigger>
              <SelectValue placeholder="Any status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Any status</SelectItem>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {statusLabel(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-36">
          <Label className="mb-1 block text-xs text-muted-foreground">Risk ≥</Label>
          <Select value={String(riskGte)} onValueChange={(v) => setRiskGte(Number(v))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {RISK_FLOORS.map((r) => (
                <SelectItem key={r} value={String(r)}>
                  {r === 0 ? 'Any risk' : `≥ ${r}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-44">
          <Label htmlFor="triage-assignee" className="mb-1 block text-xs text-muted-foreground">
            Assignee
          </Label>
          <Input
            id="triage-assignee"
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            placeholder="Any assignee"
          />
        </div>

        <div className="w-44">
          <Label htmlFor="triage-type" className="mb-1 block text-xs text-muted-foreground">
            Type
          </Label>
          <Input
            id="triage-type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            placeholder="Alert type"
          />
        </div>

        {filtersActive ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={resetFilters}
            className="text-muted-foreground"
          >
            <Filter className="size-3.5" /> Clear
          </Button>
        ) : null}
      </div>

      {/* ── summary line ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="secondary" className="tabular-nums">
          {rows.length} {dedupe ? 'entities' : 'alerts'}
        </Badge>
        <span>of {total} open</span>
        {dedupe && collapsed > 0 ? <span>· {collapsed} duplicates collapsed</span> : null}
        {mayTriage ? null : (
          <span className="text-amber-500/90">· read-only role — claim disabled</span>
        )}
      </div>

      {/* ── table ────────────────────────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
        {/* sticky header — one cell per AlertRow grid column, in order. */}
        <div
          role="row"
          className={cn(
            ALERT_ROW_GRID,
            'border-b border-border bg-muted/30 px-3 py-2 pl-4 text-xs font-medium text-muted-foreground',
          )}
        >
          <SortHeader {...headerProps('risk_score')} className="justify-center" />
          <SortHeader {...headerProps('composite')} />
          <span>Entity</span>
          <span>Title / type</span>
          <SortHeader {...headerProps('exposure_inr')} className="justify-end text-right" />
          <SortHeader {...headerProps('confidence')} />
          <span>Layers</span>
          <SortHeader {...headerProps('sla')} />
          <span>Assignee</span>
          <span className="text-right">Action</span>
        </div>

        <QueryBoundary
          isLoading={alertsQuery.isLoading}
          isError={alertsQuery.isError}
          error={alertsQuery.error}
          onRetry={() => void alertsQuery.refetch()}
          skeleton={<QueueSkeleton />}
        >
          {sortedRows.length === 0 ? (
            <EmptyState
              icon={Inbox}
              title={filtersActive ? 'No alerts match your filters' : 'Queue is clear'}
              description={
                filtersActive
                  ? 'Loosen the filters above to see more of the queue.'
                  : 'No open alerts are waiting for triage right now.'
              }
              action={
                filtersActive ? (
                  <Button variant="outline" size="sm" onClick={resetFilters}>
                    Clear filters
                  </Button>
                ) : undefined
              }
              className="m-3 flex-1"
            />
          ) : (
            <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto">
              <div
                style={{ height: `${virtualizer.getTotalSize()}px` }}
                className="relative w-full"
              >
                {virtualItems.map((vi) => {
                  const row = sortedRows[vi.index].original
                  return (
                    <div
                      key={row.alert.alert_id}
                      data-index={vi.index}
                      ref={virtualizer.measureElement}
                      className="absolute inset-x-0 top-0"
                      style={{ transform: `translateY(${vi.start}px)` }}
                    >
                      <AlertRow
                        alert={row.alert}
                        duplicateCount={dedupe ? row.group.length - 1 : 0}
                        canClaim={mayTriage}
                        claiming={claim.isPending && claim.variables === row.alert.alert_id}
                        onOpen={(a) => navigate(`/alerts/${a.alert_id}`)}
                        onClaim={(a) => claim.mutate(a.alert_id)}
                      />
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </QueryBoundary>
      </div>
    </div>
  )
}

/* ── sortable column header cell ──────────────────────────────────────────── */
function SortHeader({
  label,
  active,
  dir,
  onClick,
  className,
}: {
  label: string
  active: boolean
  dir: 'asc' | 'desc'
  onClick: () => void
  className?: string
}) {
  const Icon = !active ? ArrowUpDown : dir === 'desc' ? ArrowDownNarrowWide : ArrowUpNarrowWide
  return (
    <button
      type="button"
      onClick={onClick}
      aria-sort={active ? (dir === 'desc' ? 'descending' : 'ascending') : 'none'}
      className={cn(
        'inline-flex items-center gap-1 rounded px-1 py-0.5 text-left transition-colors hover:text-foreground focus-ring',
        active && 'text-foreground',
        className,
      )}
    >
      {label}
      <Icon className={cn('size-3', active ? 'opacity-100' : 'opacity-50')} />
    </button>
  )
}

/* ── skeleton mirroring the row grid ──────────────────────────────────────── */
function QueueSkeleton() {
  return (
    <div className="divide-y divide-border">
      {Array.from({ length: 10 }).map((_, i) => (
        <div key={i} className={cn(ALERT_ROW_GRID, 'px-3 py-2.5 pl-4')}>
          <Skeleton className="mx-auto size-8 rounded-full" />
          <Skeleton className="h-5 w-16" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-40" />
          <Skeleton className="ml-auto h-4 w-14" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="ml-auto h-7 w-16" />
        </div>
      ))}
    </div>
  )
}
