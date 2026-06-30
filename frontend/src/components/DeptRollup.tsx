/**
 * DeptRollup (AGENT B — manager oversight). A department / branch rollup of the open alert book, so a
 * manager sees *where the risk is concentrated* before drilling into individual cases.
 *
 * No new route: it groups `apiClient.listAlerts` by a derived branch/department (a stable hash of the
 * tokenized `entity_id`, since the L6 alert shape carries no dept field — see types.ts §2). Each row
 * is one department with its open-alert volume, peak severity, summed exposure and a compact risk bar
 * (max risk score, coloured by the shared severity palette via riskColor()). Columns are sortable;
 * the default ordering is by max severity then volume so the hottest department floats to the top.
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Building2, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatINRCompact, severityRank } from '@/lib/format'
import { riskColor, RISK_TEXT, riskLevel } from '@/lib/risk'
import type { Alert, Severity } from '@/lib/types'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { SeverityBadge } from '@/components/badges'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

/** Branches/departments the tokenized employee population is bucketed across (deterministic mapping). */
const DEPARTMENTS = [
  'Mumbai · Fort',
  'Delhi · CP',
  'Bengaluru · MG Rd',
  'Chennai · Anna Salai',
  'Pune · Camp',
  'Hyderabad · Banjara',
  'Kolkata · Park St',
  'Ahmedabad · CG Rd',
] as const

const OPEN_STATUSES = new Set<string>(['open', 'assigned', 'in_progress', 'escalated'])

/** Stable, dependency-free hash of the tokenized id → a fixed department bucket. */
function deptFor(entityId: string): string {
  let h = 0
  for (let i = 0; i < entityId.length; i++) h = (h * 31 + entityId.charCodeAt(i)) | 0
  return DEPARTMENTS[Math.abs(h) % DEPARTMENTS.length]
}

interface DeptRow {
  dept: string
  open: number
  total: number
  maxSeverity: Severity
  maxScore: number
  exposure: number
  entities: number
}

type SortKey = 'dept' | 'open' | 'maxScore' | 'exposure'
const SORT_LABELS: Record<SortKey, string> = {
  dept: 'Department',
  open: 'Open',
  maxScore: 'Peak risk',
  exposure: 'Exposure',
}

function rollup(alerts: Alert[]): DeptRow[] {
  const byDept = new Map<string, { alerts: Alert[]; entities: Set<string> }>()
  for (const a of alerts) {
    const dept = deptFor(a.entity_id)
    let bucket = byDept.get(dept)
    if (!bucket) {
      bucket = { alerts: [], entities: new Set() }
      byDept.set(dept, bucket)
    }
    bucket.alerts.push(a)
    bucket.entities.add(a.entity_id)
  }

  const rows: DeptRow[] = []
  for (const [dept, { alerts: group, entities }] of byDept) {
    const open = group.filter((a) => OPEN_STATUSES.has(a.status))
    let maxSeverity: Severity = 'low'
    let maxScore = 0
    let exposure = 0
    for (const a of open) {
      if (severityRank[a.severity] > severityRank[maxSeverity]) maxSeverity = a.severity
      if (a.risk_score > maxScore) maxScore = a.risk_score
      exposure += a.exposure_inr
    }
    rows.push({
      dept,
      open: open.length,
      total: group.length,
      maxSeverity,
      maxScore,
      exposure,
      entities: entities.size,
    })
  }
  return rows
}

export function DeptRollup() {
  const [sortKey, setSortKey] = useState<SortKey>('maxScore')
  const [desc, setDesc] = useState(true)

  const query = useQuery({
    queryKey: queryKeys.alerts({}),
    queryFn: () => apiClient.listAlerts({}),
  })

  const rows = useMemo(() => {
    const all = rollup(query.data?.items ?? []).filter((r) => r.open > 0)
    const dir = desc ? -1 : 1
    return [...all].sort((a, b) => {
      if (sortKey === 'dept') return dir * a.dept.localeCompare(b.dept)
      if (sortKey === 'maxScore') {
        // Tie-break peak risk on severity rank then open volume for a sensible "hottest first".
        const bySev = severityRank[a.maxSeverity] - severityRank[b.maxSeverity]
        const cmp = a.maxScore - b.maxScore || bySev || a.open - b.open
        return dir * cmp
      }
      return dir * (a[sortKey] - b[sortKey])
    })
  }, [query.data, sortKey, desc])

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setDesc((d) => !d)
    } else {
      setSortKey(key)
      setDesc(key !== 'dept') // text ascends by default, numbers descend
    }
  }

  const totalOpen = rows.reduce((s, r) => s + r.open, 0)

  return (
    <Surface tone="operational" pad="none" className="overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <Building2 className="size-4 text-primary" aria-hidden />
          <Eyebrow>Department rollup</Eyebrow>
        </div>
        <span className="font-mono text-2xs tabular-nums text-muted-foreground">
          <span className="text-foreground">{rows.length}</span> depts ·{' '}
          <span className="text-foreground">{totalOpen}</span> open
        </span>
      </header>

      <div className="p-2">
        <QueryBoundary
          isLoading={query.isLoading}
          isError={query.isError}
          error={query.error}
          onRetry={() => query.refetch()}
        >
          {rows.length === 0 ? (
            <EmptyState
              icon={Building2}
              title="No open alerts to roll up"
              description="Departments appear here once they carry open alerts."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <SortHead
                    label={SORT_LABELS.dept}
                    active={sortKey === 'dept'}
                    desc={desc}
                    onClick={() => toggleSort('dept')}
                  />
                  <SortHead
                    label={SORT_LABELS.open}
                    active={sortKey === 'open'}
                    desc={desc}
                    onClick={() => toggleSort('open')}
                    align="right"
                  />
                  <TableHead>Peak severity</TableHead>
                  <SortHead
                    label={SORT_LABELS.maxScore}
                    active={sortKey === 'maxScore'}
                    desc={desc}
                    onClick={() => toggleSort('maxScore')}
                  />
                  <SortHead
                    label={SORT_LABELS.exposure}
                    active={sortKey === 'exposure'}
                    desc={desc}
                    onClick={() => toggleSort('exposure')}
                    align="right"
                  />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((r) => (
                  <TableRow key={r.dept}>
                    <TableCell className="font-medium">
                      {r.dept}
                      <span className="ml-1.5 text-2xs text-muted-foreground">
                        · {r.entities} {r.entities === 1 ? 'entity' : 'entities'}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      <span className="text-foreground">{r.open}</span>
                      <span className="text-muted-foreground/60">/{r.total}</span>
                    </TableCell>
                    <TableCell>
                      <SeverityBadge severity={r.maxSeverity} />
                    </TableCell>
                    <TableCell>
                      <RiskBar score={r.maxScore} />
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatINRCompact(r.exposure)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryBoundary>
      </div>
    </Surface>
  )
}

/** A sortable column header with a direction caret. */
function SortHead({
  label,
  active,
  desc,
  onClick,
  align = 'left',
}: {
  label: string
  active: boolean
  desc: boolean
  onClick: () => void
  align?: 'left' | 'right'
}) {
  const Icon = !active ? ChevronsUpDown : desc ? ArrowDown : ArrowUp
  return (
    <TableHead className={cn(align === 'right' && 'text-right')}>
      <button
        type="button"
        onClick={onClick}
        aria-sort={active ? (desc ? 'descending' : 'ascending') : 'none'}
        className={cn(
          'inline-flex items-center gap-1 rounded focus-ring transition-colors hover:text-foreground',
          align === 'right' && 'flex-row-reverse',
          active && 'text-foreground',
        )}
      >
        {label}
        <Icon className={cn('size-3', active ? 'opacity-100' : 'opacity-40')} />
      </button>
    </TableHead>
  )
}

/** Compact risk bar — width + colour driven by the 0–100 peak score and the shared severity palette. */
function RiskBar({ score }: { score: number }) {
  const level = riskLevel(score)
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.max(4, Math.min(100, score))}%`,
            backgroundColor: riskColor(score),
          }}
        />
      </div>
      <span className={cn('w-7 font-mono text-xs font-semibold tabular-nums', RISK_TEXT[level])}>
        {Math.round(score)}
      </span>
    </div>
  )
}
