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
import { Fragment, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Building2, ChevronRight, ChevronsUpDown, Info } from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatINRCompact, formatRelative, severityRank } from '@/lib/format'
import { riskColor, RISK_TEXT, riskLevel } from '@/lib/risk'
import type { Alert, Severity } from '@/lib/types'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { SeverityBadge } from '@/components/badges'
import { MaskedPII } from '@/components/MaskedPII'
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
  items: Alert[] // the open alerts in this dept, highest-risk first (for the drill-in)
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
      items: [...open].sort((a, b) => b.risk_score - a.risk_score),
    })
  }
  return rows
}

export function DeptRollup() {
  const [sortKey, setSortKey] = useState<SortKey>('maxScore')
  const [desc, setDesc] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

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
      <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Building2 className="size-4 text-primary" aria-hidden />
            <Eyebrow>Department rollup</Eyebrow>
          </div>
          <p className="mt-0.5 text-2xs text-muted-foreground">
            Where is risk concentrated? Open-alert volume, peak severity and exposure by branch —
            click a row to see its alerts.
          </p>
        </div>
        <span className="shrink-0 font-mono text-2xs tabular-nums text-muted-foreground">
          <span className="text-foreground">{rows.length}</span> depts ·{' '}
          <span className="text-foreground">{totalOpen}</span> open
        </span>
      </header>

      {/* How to read this — brief guidance so the numbers are self-explanatory. */}
      <div className="flex items-start gap-2 border-b border-border/60 bg-muted/20 px-4 py-2 text-2xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" />
        <p>
          <span className="font-medium text-foreground">Open X/Y</span> = X unresolved of Y total ·{' '}
          <span className="font-medium text-foreground">Peak risk</span> = highest 0–100 score in
          the branch · <span className="font-medium text-foreground">Exposure</span> = ₹ at risk
          across open alerts. Sort by Peak risk for the hottest branch, or Exposure for the largest
          ₹.
        </p>
      </div>

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
                {rows.map((r) => {
                  const isOpen = expanded === r.dept
                  return (
                    <Fragment key={r.dept}>
                      <TableRow
                        className="cursor-pointer"
                        onClick={() => setExpanded((d) => (d === r.dept ? null : r.dept))}
                        aria-expanded={isOpen}
                        title={`Show ${r.open} open alert${r.open === 1 ? '' : 's'} in ${r.dept}`}
                      >
                        <TableCell className="font-medium">
                          <span className="inline-flex items-center gap-1.5">
                            <ChevronRight
                              className={cn(
                                'size-3.5 text-muted-foreground transition-transform',
                                isOpen && 'rotate-90',
                              )}
                            />
                            {r.dept}
                          </span>
                          <span className="ml-1.5 text-2xs text-muted-foreground">
                            · {r.entities} {r.entities === 1 ? 'entity' : 'entities'}
                          </span>
                        </TableCell>
                        <TableCell
                          className="text-right font-mono tabular-nums"
                          title={`${r.open} unresolved (open/assigned/in-progress/escalated) of ${r.total} total`}
                        >
                          <span className="text-foreground">{r.open}</span>
                          <span className="text-muted-foreground/60">/{r.total}</span>
                        </TableCell>
                        <TableCell title="Highest severity among this branch's open alerts">
                          <SeverityBadge severity={r.maxSeverity} />
                        </TableCell>
                        <TableCell title="Highest 0–100 fused risk score in this branch">
                          <RiskBar score={r.maxScore} />
                        </TableCell>
                        <TableCell
                          className="text-right font-mono tabular-nums"
                          title="Total ₹ exposure across this branch's open alerts"
                        >
                          {formatINRCompact(r.exposure)}
                        </TableCell>
                      </TableRow>
                      {isOpen ? (
                        <TableRow className="hover:bg-transparent">
                          <TableCell colSpan={5} className="bg-muted/20 p-0">
                            <ul className="divide-y divide-border/50">
                              {r.items.slice(0, 6).map((a) => (
                                <li key={a.alert_id}>
                                  <Link
                                    to={`/alerts/${a.alert_id}`}
                                    className="focus-ring flex items-center gap-3 px-4 py-1.5 text-2xs hover:bg-accent/40"
                                  >
                                    <span
                                      className="w-7 shrink-0 text-right font-mono font-semibold tabular-nums"
                                      style={{ color: riskColor(a.risk_score) }}
                                    >
                                      {a.risk_score}
                                    </span>
                                    <span className="w-24 shrink-0 truncate">
                                      <MaskedPII
                                        value={a.entity_id}
                                        entityId={a.entity_id}
                                        alertId={a.alert_id}
                                      />
                                    </span>
                                    <span className="min-w-0 flex-1 truncate text-muted-foreground">
                                      {a.title ?? 'Alert'}
                                    </span>
                                    <span className="shrink-0 tabular-nums text-muted-foreground">
                                      {formatINRCompact(a.exposure_inr)}
                                    </span>
                                    <span
                                      className="shrink-0 tabular-nums text-muted-foreground/70"
                                      title={a.created_ts}
                                    >
                                      {formatRelative(a.created_ts)}
                                    </span>
                                  </Link>
                                </li>
                              ))}
                              {r.items.length > 6 ? (
                                <li className="px-4 py-1.5 text-2xs text-muted-foreground">
                                  +{r.items.length - 6} more open in this branch
                                </li>
                              ) : null}
                            </ul>
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </Fragment>
                  )
                })}
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
