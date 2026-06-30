/**
 * Auditor view (FRONTEND-13; blueprint Part 24.4 screen 6 + Part 24.2 RBAC).
 *
 * A **read-only** window onto the immutable WORM audit trail (`GET /audit`). The Chief Internal
 * Auditor role holds `view_audit: full` and nothing else — there are deliberately **no** mutation
 * controls here. The whole point is "watch-the-watchers": every actor, including investigators and
 * even other auditors, is logged. Filters narrow by actor / entity / action / date; the table
 * highlights the two accountability-critical action families (who-viewed-which-employee,
 * who-closed-what).
 */
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Eye, FileSearch, Gavel, Lock, ScrollText, ShieldCheck } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatIST } from '@/lib/format'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AuditTable } from '@/components/AuditTable'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { AuditQuery } from '@/lib/types'

const ACTION_FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: 'All actions' },
  { value: 'view_entity', label: 'Viewed employee (entity-360)' },
  { value: 'unmask_pii', label: 'Unmasked PII' },
  { value: 'disposition', label: 'Dispositioned alert' },
  { value: 'close_alert', label: 'Closed alert' },
  { value: 'assign', label: 'Assigned alert' },
  { value: 'block_request', label: 'Requested block' },
  { value: 'promote_model', label: 'Promoted model' },
  { value: 'rule_change_proposed', label: 'Proposed rule change' },
  { value: 'create_user', label: 'Provisioned user' },
  { value: 'view_audit', label: 'Viewed audit log' },
]

interface DraftFilters {
  actor: string
  entity: string
  action: string
  from: string
  to: string
}

const EMPTY: DraftFilters = { actor: '', entity: '', action: 'all', from: '', to: '' }

/** A `datetime-local` value (no zone) → an ISO UTC instant the API understands. */
function toIso(local: string): string | undefined {
  if (!local) return undefined
  const d = new Date(local)
  return Number.isNaN(d.getTime()) ? undefined : d.toISOString()
}

function AuditSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}

export function AuditorView() {
  const [draft, setDraft] = useState<DraftFilters>(EMPTY)
  const [applied, setApplied] = useState<AuditQuery>({})

  const auditQuery = useQuery({
    queryKey: queryKeys.audit(applied),
    queryFn: () => apiClient.getAudit(applied),
  })

  const events = useMemo(() => auditQuery.data?.items ?? [], [auditQuery.data])
  const total = auditQuery.data?.total ?? events.length

  const counts = useMemo(() => {
    let views = 0
    let unmasks = 0
    let decisions = 0
    for (const e of events) {
      if (e.action === 'view_entity') views += 1
      else if (e.action === 'unmask_pii') unmasks += 1
      else if (e.action === 'disposition' || e.action === 'close_alert' || e.action === 'close')
        decisions += 1
    }
    return { views, unmasks, decisions }
  }, [events])

  function apply() {
    setApplied({
      actor: draft.actor.trim() || undefined,
      entity: draft.entity.trim() || undefined,
      action: draft.action === 'all' ? undefined : draft.action,
      from: toIso(draft.from),
      to: toIso(draft.to),
    })
  }

  function reset() {
    setDraft(EMPTY)
    setApplied({})
  }

  const hasFilters =
    Boolean(applied.actor) ||
    Boolean(applied.entity) ||
    Boolean(applied.action) ||
    Boolean(applied.from) ||
    Boolean(applied.to)

  return (
    <div className="space-y-4">
      <PageHeader
        icon={<FileSearch className="size-5" />}
        title="Audit trail"
        description="Immutable, append-only WORM log of every action in the console. Read-only by design."
        actions={
          <Badge variant="outline" className="gap-1.5">
            <Lock className="size-3.5" /> Read-only · WORM
          </Badge>
        }
      />

      {/* Watch-the-watchers banner */}
      <div className="flex items-start gap-2.5 rounded-lg border border-tee/30 bg-tee/5 px-3.5 py-2.5 text-sm">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-tee" />
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">Watch the watchers.</span> Everyone is
          audited — relationship &amp; branch managers, cluster heads, vigilance and compliance,
          data science, risk and board, and the auditors themselves alike. This trail cannot be
          edited or deleted from the console; it records who viewed which employee and who closed
          what.
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="grid grid-cols-1 gap-3 p-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="space-y-1">
            <Label htmlFor="audit-actor" className="text-xs">
              Actor
            </Label>
            <Input
              id="audit-actor"
              placeholder="e.g. branch.demo"
              value={draft.actor}
              onChange={(e) => setDraft((d) => ({ ...d, actor: e.target.value }))}
              onKeyDown={(e) => e.key === 'Enter' && apply()}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-entity" className="text-xs">
              Entity / employee
            </Label>
            <Input
              id="audit-entity"
              placeholder="e.g. EMP-7f3a"
              value={draft.entity}
              onChange={(e) => setDraft((d) => ({ ...d, entity: e.target.value }))}
              onKeyDown={(e) => e.key === 'Enter' && apply()}
            />
          </div>
          <div className="space-y-1 lg:col-span-2">
            <Label className="text-xs">Action</Label>
            <Select
              value={draft.action}
              onValueChange={(v) => setDraft((d) => ({ ...d, action: v }))}
            >
              <SelectTrigger aria-label="Filter by action">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACTION_FILTERS.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    {f.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-from" className="text-xs">
              From
            </Label>
            <Input
              id="audit-from"
              type="datetime-local"
              value={draft.from}
              onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="audit-to" className="text-xs">
              To
            </Label>
            <Input
              id="audit-to"
              type="datetime-local"
              value={draft.to}
              onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))}
            />
          </div>
          <div className="flex items-end gap-2 sm:col-span-2 lg:col-span-6">
            <Button onClick={apply}>
              <FileSearch className="size-4" /> Apply filters
            </Button>
            <Button variant="ghost" onClick={reset} disabled={!hasFilters && draft === EMPTY}>
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Highlight counters */}
      {!auditQuery.isLoading && !auditQuery.isError ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Counter
            icon={<ScrollText className="size-4" />}
            label="Events shown"
            value={String(total)}
          />
          <Counter
            icon={<Eye className="size-4" />}
            label="Employee views"
            value={String(counts.views)}
            tone="info"
          />
          <Counter
            icon={<Lock className="size-4" />}
            label="PII unmasks"
            value={String(counts.unmasks)}
            tone={counts.unmasks > 0 ? 'warn' : undefined}
          />
          <Counter
            icon={<Gavel className="size-4" />}
            label="Case decisions"
            value={String(counts.decisions)}
          />
        </div>
      ) : null}

      <Card>
        <CardContent className="p-0">
          <QueryBoundary
            isLoading={auditQuery.isLoading}
            isError={auditQuery.isError}
            error={auditQuery.error}
            onRetry={() => void auditQuery.refetch()}
            skeleton={<AuditSkeleton />}
          >
            <AuditTable events={events} />
          </QueryBoundary>
        </CardContent>
      </Card>

      <p className="text-[0.7rem] text-muted-foreground">
        {auditQuery.dataUpdatedAt
          ? `Snapshot taken ${formatIST(new Date(auditQuery.dataUpdatedAt))}.`
          : null}{' '}
        The authoritative WORM store retains the full, hash-chained record server-side.
      </p>
    </div>
  )
}

function Counter({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode
  label: string
  value: string
  tone?: 'info' | 'warn'
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-2 p-3">
        <div>
          <p className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">{label}</p>
          <p
            className={[
              'mt-0.5 text-lg font-semibold tabular-nums',
              tone === 'warn' ? 'text-severity-high' : tone === 'info' ? 'text-reason-shap' : '',
            ].join(' ')}
          >
            {value}
          </p>
        </div>
        <span className="text-muted-foreground">{icon}</span>
      </CardContent>
    </Card>
  )
}
