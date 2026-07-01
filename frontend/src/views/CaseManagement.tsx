import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, FolderOpen, Inbox, Layers } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatINR, formatRelative, severityRank, statusLabel } from '@/lib/format'
import { cn } from '@/lib/cn'
import { PageHeader } from '@/components/PageHeader'
import { CasesTriageHint } from '@/components/CasesTriageHint'
import { QueryBoundary } from '@/components/QueryBoundary'
import { MaskedPII } from '@/components/MaskedPII'
import { SeverityBadge, StatusBadge } from '@/components/badges'
import { Card, CardContent } from '@/components/ui/card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { AmountFlip, CountUp, RouteTransition, SlaRing, useAutoAnimateList } from '@/ui'
import type { CaseStatus, CaseSummary } from '@/lib/types'

const STATUS_FILTERS: { value: 'all' | CaseStatus; label: string }[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'escalated', label: 'Escalated' },
  { value: 'closed', label: 'Closed' },
]

/** Cases sort by open-first, then severity, then most-recently updated — the triage-relevant order. */
const STATUS_ORDER: Record<CaseStatus, number> = {
  escalated: 0,
  in_progress: 1,
  open: 2,
  closed: 3,
}

function assigneeInitials(assignee: string): string {
  const parts = assignee.replace(/[_-]+/g, ' ').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function CaseTableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}

/**
 * Case management list (FRONTEND-5; blueprint Part 24.4 screen 4, l.955). Lists `apiClient.listCases()`
 * with status filtering; each row navigates to `/cases/{case_id}`. Money is INR-compact, entity tokens
 * are rendered masked, and SLA/severity reuse the shared domain badges.
 */
export function CaseManagement() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState<'all' | CaseStatus>('all')

  const casesQuery = useQuery({
    queryKey: queryKeys.cases(),
    queryFn: () => apiClient.listCases(),
  })

  const allCases = useMemo(() => casesQuery.data?.items ?? [], [casesQuery.data])

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = {}
    let exposure = 0
    for (const c of allCases) {
      byStatus[c.status] = (byStatus[c.status] ?? 0) + 1
      exposure += c.exposure_inr ?? 0
    }
    const openLike = (byStatus.open ?? 0) + (byStatus.in_progress ?? 0) + (byStatus.escalated ?? 0)
    return { total: allCases.length, openLike, escalated: byStatus.escalated ?? 0, exposure }
  }, [allCases])

  const visible = useMemo(() => {
    const filtered =
      statusFilter === 'all' ? allCases : allCases.filter((c) => c.status === statusFilter)
    return [...filtered].sort((a, b) => {
      const statusDelta = STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
      if (statusDelta !== 0) return statusDelta
      const sevDelta = severityRank[b.severity] - severityRank[a.severity]
      if (sevDelta !== 0) return sevDelta
      return +new Date(b.updated_ts) - +new Date(a.updated_ts)
    })
  }, [allCases, statusFilter])

  const [listRef] = useAutoAnimateList<HTMLTableSectionElement>()

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<Briefcase className="size-5" />}
        title="Case management"
        description="Investigation cases grouping related alerts. Click a case to triage, note, and disposition — nothing auto-blocks or auto-closes."
        actions={
          <Select
            value={statusFilter}
            onValueChange={(v) => setStatusFilter(v as 'all' | CaseStatus)}
          >
            <SelectTrigger className="w-44" aria-label="Filter cases by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <CasesTriageHint />

      {!casesQuery.isLoading && !casesQuery.isError ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <SummaryStat
            label="Total cases"
            value={<CountUp value={counts.total} />}
            icon={<Layers className="size-4" />}
          />
          <SummaryStat
            label="Active"
            value={<CountUp value={counts.openLike} />}
            icon={<FolderOpen className="size-4" />}
          />
          <SummaryStat
            label="Escalated"
            value={<CountUp value={counts.escalated} />}
            icon={<Inbox className="size-4" />}
            tone={counts.escalated > 0 ? 'warn' : undefined}
          />
          <SummaryStat
            label="Total exposure"
            value={<AmountFlip value={counts.exposure} kind="inr" compact />}
            title={formatINR(counts.exposure)}
          />
        </div>
      ) : null}

      <Card>
        <CardContent className="p-0">
          <QueryBoundary
            isLoading={casesQuery.isLoading}
            isError={casesQuery.isError}
            error={casesQuery.error}
            onRetry={() => void casesQuery.refetch()}
            skeleton={
              <div className="p-4">
                <CaseTableSkeleton />
              </div>
            }
          >
            {visible.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  icon={FolderOpen}
                  title={
                    statusFilter === 'all'
                      ? 'No cases'
                      : `No ${statusLabel(statusFilter).toLowerCase()} cases`
                  }
                  description={
                    statusFilter === 'all'
                      ? 'Cases appear here when alerts are grouped for investigation.'
                      : 'Try a different status filter to see other cases.'
                  }
                />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="min-w-[15rem]">Case</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Alerts</TableHead>
                    <TableHead className="text-right">Exposure</TableHead>
                    <TableHead>Assignee</TableHead>
                    <TableHead>SLA</TableHead>
                    <TableHead className="text-right">Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody ref={listRef}>
                  {visible.map((c) => (
                    <CaseRow key={c.case_id} c={c} onOpen={() => navigate(`/cases/${c.case_id}`)} />
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>
    </RouteTransition>
  )
}

function SummaryStat({
  label,
  value,
  icon,
  tone,
  title,
}: {
  label: string
  value: React.ReactNode
  icon?: React.ReactNode
  tone?: 'warn'
  title?: string
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-2 p-3">
        <div>
          <Eyebrow>{label}</Eyebrow>
          <p
            className={cn(
              'mt-0.5 font-mono text-lg font-semibold tabular-nums',
              tone === 'warn' && 'text-severity-high',
            )}
            title={title}
          >
            {value}
          </p>
        </div>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </CardContent>
    </Card>
  )
}

function CaseRow({ c, onOpen }: { c: CaseSummary; onOpen: () => void }) {
  return (
    <TableRow
      className="cursor-pointer"
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === 'Enter') onOpen()
      }}
      tabIndex={0}
      role="link"
      aria-label={`Open case ${c.title}`}
    >
      <TableCell>
        <div className="flex items-center gap-2.5">
          <SeverityBadge severity={c.severity} className="shrink-0" />
          <div className="min-w-0">
            <Link
              to={`/cases/${c.case_id}`}
              onClick={(e) => e.stopPropagation()}
              className="block truncate font-medium hover:underline"
            >
              {c.title}
            </Link>
            <span className="font-mono text-[0.7rem] tabular-nums text-muted-foreground">
              {c.case_id}
            </span>
          </div>
        </div>
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        <MaskedPII value={c.entity_id} entityId={c.entity_id} />
      </TableCell>
      <TableCell>
        <StatusBadge status={c.status} />
      </TableCell>
      <TableCell className="text-right tabular-nums">
        <Badge variant="secondary" className="font-mono">
          {c.alert_ids.length}
        </Badge>
      </TableCell>
      <TableCell
        className="text-right font-medium tabular-nums"
        title={formatINR(c.exposure_inr ?? 0)}
      >
        <AmountFlip
          value={c.exposure_inr ?? 0}
          kind="inr"
          compact
          className="text-sm font-medium text-foreground"
        />
      </TableCell>
      <TableCell>
        {c.assignee ? (
          <div className="flex items-center gap-1.5">
            <Avatar className="size-6">
              <AvatarFallback className="text-[0.6rem]">
                {assigneeInitials(c.assignee)}
              </AvatarFallback>
            </Avatar>
            <span className="truncate text-xs">{c.assignee}</span>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">Unassigned</span>
        )}
      </TableCell>
      <TableCell>
        {c.sla_due_ts ? (
          <SlaRing dueTs={c.sla_due_ts} size={34} />
        ) : (
          <span className="font-mono text-xs text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums text-muted-foreground">
        {formatRelative(c.updated_ts)}
      </TableCell>
    </TableRow>
  )
}
