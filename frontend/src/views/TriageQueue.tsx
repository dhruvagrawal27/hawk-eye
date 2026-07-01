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
import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownNarrowWide,
  ArrowUp,
  ArrowUpDown,
  ArrowUpNarrowWide,
  Filter,
  Inbox,
  ListChecks,
  RotateCw,
  Search,
  UserPlus2,
  X,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { compositePriority, slaInfo, statusLabel } from '@/lib/format'
import type { Alert, AlertQuery, AlertStatus } from '@/lib/types'
import { useAuth } from '@/auth/rbac'
import { PageHeader } from '@/components/PageHeader'
import { CasesTriageHint } from '@/components/CasesTriageHint'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AlertRow, ALERT_ROW_GRID } from '@/components/AlertRow'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Checkbox } from '@/components/ui/checkbox'
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
import { RouteTransition, useAutoAnimateList } from '@/ui'

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

  /**
   * SAVED VIEWS — the active filters/sort live in the URL (`useSearchParams`) so a configured view
   * is shareable, bookmarkable, and survives reload. The URL is the single source of truth; setters
   * write back to it (omitting defaults to keep links clean). `replace` avoids polluting history on
   * every keystroke.
   */
  const [params, setParams] = useSearchParams()

  const status = (params.get('status') ?? '') as AlertStatus | ''
  const riskGte = Number(params.get('risk_gte') ?? 0) || 0
  const assignee = params.get('assignee') ?? ''
  const type = params.get('type') ?? ''
  const search = params.get('q') ?? ''
  const dedupe = params.get('dedupe') !== '0' // dedupe is on by default
  const sortKey = (params.get('sort') ?? 'composite') as SortKey
  const sort = {
    key: SORT_KEYS.includes(sortKey) ? sortKey : 'composite',
    dir: (params.get('dir') === 'asc' ? 'asc' : 'desc') as 'asc' | 'desc',
  }

  /** Patch one or more view params at once, dropping keys set to a default/empty value. */
  const patchParams = useCallback(
    (patch: Record<string, string | null>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(patch)) {
            if (v === null || v === '') next.delete(k)
            else next.set(k, v)
          }
          return next
        },
        { replace: true },
      )
    },
    [setParams],
  )

  const setStatus = (v: AlertStatus | '') => patchParams({ status: v || null })
  const setRiskGte = (v: number) => patchParams({ risk_gte: v ? String(v) : null })
  const setAssignee = (v: string) => patchParams({ assignee: v.trim() || null })
  const setType = (v: string) => patchParams({ type: v.trim() || null })
  const setSearch = (v: string) => patchParams({ q: v || null })
  const setDedupe = (v: boolean) => patchParams({ dedupe: v ? null : '0' })

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

  /* ── sort in memory ─────────────────────────────────────────────────────────
   * Uniform rows → a plain sort + plain render (no windowing / `measureElement`). The queue is
   * deduped-per-entity and case-scoped, so the row count is bounded and renders comfortably. This
   * deliberately avoids the virtualizer's ResizeObserver measurement loop, which could peg the main
   * thread and hard-freeze the tab on this route. */
  const sortedRows = useMemo<QueueRow[]>(() => {
    const arr = [...rows]
    arr.sort((a, b) => {
      const diff = sortValue(a.alert, sort.key) - sortValue(b.alert, sort.key)
      return sort.dir === 'desc' ? -diff : diff
    })
    return arr
  }, [rows, sort.key, sort.dir])

  /* ── BULK SELECT ────────────────────────────────────────────────────────────
   * Selection is keyed by the representative row's alert_id and lives in component state (not the
   * URL — it's ephemeral, not part of the shareable view). A deduped row stands in for its whole
   * group, so bulk actions fan out over `group`. Stale ids (filtered out, refetched away) are
   * ignored when we resolve the current selection back to live rows. */
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())

  const rowById = useMemo(() => {
    const m = new Map<string, QueueRow>()
    for (const r of sortedRows) m.set(r.alert.alert_id, r)
    return m
  }, [sortedRows])

  // Only count selections that still resolve to a visible row.
  const selectedRows = useMemo(
    () => [...selectedIds].map((id) => rowById.get(id)).filter((r): r is QueueRow => Boolean(r)),
    [selectedIds, rowById],
  )
  const selectedCount = selectedRows.length
  // The set of underlying alert_ids a bulk action will touch (expands deduped groups).
  const selectedAlertIds = useMemo(
    () => selectedRows.flatMap((r) => r.group.map((a) => a.alert_id)),
    [selectedRows],
  )

  const allVisibleSelected = sortedRows.length > 0 && selectedCount === sortedRows.length
  const someVisibleSelected = selectedCount > 0 && !allVisibleSelected

  const toggleRow = useCallback((alert: Alert, next: boolean) => {
    setSelectedIds((prev) => {
      const set = new Set(prev)
      if (next) set.add(alert.alert_id)
      else set.delete(alert.alert_id)
      return set
    })
  }, [])

  const toggleSelectAll = useCallback(
    (next: boolean) => {
      setSelectedIds(next ? new Set(sortedRows.map((r) => r.alert.alert_id)) : new Set())
    },
    [sortedRows],
  )

  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])

  /* Bulk action — fans an assignment across every selected (expanded) alert via the same
   * single-alert `assign` endpoint CLAIM uses; we surface one aggregate toast. All three variants are
   * assign-only routing (claim → me, assign → a named owner, escalate → the escalation queue): never
   * a disposition, block, or close (golden rule #1 — nothing auto-blocks or auto-closes). */
  type BulkKind = 'claim' | 'assign' | 'escalate'
  const bulkAction = useMutation({
    mutationFn: async ({ assignee }: { kind: BulkKind; assignee: string }) => {
      const results = await Promise.allSettled(
        selectedAlertIds.map((id) => apiClient.assignAlert(id, { assignee })),
      )
      const ok = results.filter((r) => r.status === 'fulfilled').length
      return { ok, failed: results.length - ok }
    },
    onSuccess: ({ ok, failed }, { kind }) => {
      const verb = kind === 'escalate' ? 'Escalated' : kind === 'assign' ? 'Assigned' : 'Claimed'
      if (failed === 0) toast.success(`${verb} ${ok} alert${ok === 1 ? '' : 's'}`)
      else
        toast.warning(`${verb} ${ok}/${ok + failed} alerts`, {
          description: `${failed} could not be updated.`,
        })
      clearSelection()
      void queryClient.invalidateQueries({ queryKey: ['alerts'] })
    },
    onError: (err) =>
      toast.error('Bulk action failed', {
        description:
          err instanceof ApiError ? err.message : 'Could not update the selected alerts.',
      }),
  })

  const runBulk = useCallback(
    (kind: BulkKind) => {
      if (selectedAlertIds.length === 0) return
      let assignee: string
      if (kind === 'claim') assignee = user?.username ?? 'me'
      else if (kind === 'escalate') assignee = 'escalation'
      else {
        const input = window.prompt('Assign selected alerts to (username):', '')?.trim()
        if (!input) return
        assignee = input
      }
      bulkAction.mutate({ kind, assignee })
    },
    [bulkAction, selectedAlertIds, user],
  )

  // AutoAnimate the row list so alerts entering/leaving (arrival, claim, disposition, filter) glide
  // instead of jumping — reduced-motion disables it. Motion stays off the scroll hot path (rows only
  // animate on add/remove/reorder, never on scroll).
  const [listRef] = useAutoAnimateList<HTMLDivElement>()

  const total = alertsQuery.data?.total ?? allAlerts.length
  const collapsed = allAlerts.length - rows.length
  const filtersActive = Boolean(status || riskGte || assignee || type || search)

  function toggleSort(key: SortKey) {
    const dir = sort.key === key && sort.dir === 'desc' ? 'asc' : 'desc'
    // 'composite' desc is the default view, so encode it as a clean URL (no sort/dir params).
    patchParams({
      sort: key === 'composite' && dir === 'desc' ? null : key,
      dir: dir === 'desc' ? null : 'asc',
    })
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
    // Clear filter params but keep sort/dedupe (the "view" shape) intact.
    patchParams({ status: null, risk_gte: null, assignee: null, type: null, q: null })
  }

  return (
    <RouteTransition className="flex h-full flex-col gap-3">
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

      <CasesTriageHint />

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

      {/* ── bulk action bar — gated on triage; acts on the expanded selection ──── */}
      {mayTriage && selectedCount > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/[0.06] px-3 py-2">
          <Badge variant="default" className="tabular-nums">
            {selectedCount} selected
          </Badge>
          {selectedAlertIds.length !== selectedCount ? (
            <span className="text-xs text-muted-foreground">
              · {selectedAlertIds.length} alerts (groups expanded)
            </span>
          ) : null}
          <div className="ml-auto flex items-center gap-1.5">
            <Button
              size="sm"
              variant="secondary"
              disabled={bulkAction.isPending}
              onClick={() => runBulk('claim')}
            >
              <UserPlus2 className="size-3.5" /> Claim
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={bulkAction.isPending}
              onClick={() => runBulk('assign')}
            >
              <UserPlus2 className="size-3.5" /> Assign…
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={bulkAction.isPending}
              onClick={() => runBulk('escalate')}
            >
              <ArrowUp className="size-3.5" /> Escalate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="text-muted-foreground"
              onClick={clearSelection}
              aria-label="Clear selection"
            >
              <X className="size-3.5" /> Clear
            </Button>
          </div>
        </div>
      ) : null}

      {/* ── table ────────────────────────────────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
        {/* One scroll area — vertical for rows; horizontal for the dense grid on narrow screens
            (the min-width keeps every column reachable instead of clipping them). */}
        <div className="min-h-0 flex-1 overflow-auto">
          <div className="min-w-[72rem]">
            {/* sticky header — one cell per AlertRow grid column, in order. */}
            <div
              role="row"
              className={cn(
                ALERT_ROW_GRID,
                'sticky top-0 z-10 border-b border-border bg-muted px-3 py-2 pl-4 text-xs font-medium text-muted-foreground',
              )}
            >
              <span className="flex justify-center">
                {mayTriage ? (
                  <Checkbox
                    checked={
                      allVisibleSelected ? true : someVisibleSelected ? 'indeterminate' : false
                    }
                    onCheckedChange={(v) => toggleSelectAll(v === true)}
                    aria-label="Select all visible alerts"
                  />
                ) : null}
              </span>
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
                <div ref={listRef}>
                  {sortedRows.map((row) => (
                    <AlertRow
                      key={row.alert.alert_id}
                      alert={row.alert}
                      duplicateCount={dedupe ? row.group.length - 1 : 0}
                      canClaim={mayTriage}
                      claiming={claim.isPending && claim.variables === row.alert.alert_id}
                      selectable={mayTriage}
                      selected={selectedIds.has(row.alert.alert_id)}
                      onSelectChange={toggleRow}
                      onOpen={(a) => navigate(`/alerts/${a.alert_id}`)}
                      onClaim={(a) => claim.mutate(a.alert_id)}
                    />
                  ))}
                </div>
              )}
            </QueryBoundary>
          </div>
        </div>
      </div>
    </RouteTransition>
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
          <Skeleton className="mx-auto size-4 rounded" />
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
