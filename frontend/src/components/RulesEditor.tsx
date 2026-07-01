import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ChevronDown,
  ChevronRight,
  GitCommitVertical,
  History,
  Loader2,
  Lock,
  PencilLine,
  ScrollText,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { formatIST, formatRelative, humanize } from '@/lib/format'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/rbac'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { InfoTip } from '@/components/ui/tooltip'
import { toast } from '@/components/ui/toaster'
import { useAutoAnimateList } from '@/ui'
import type { Rule, RuleChange, RuleParam, RuleStatus, RuleType } from '@/lib/types'

/* ── Rule status → badge variant / label (change-control lifecycle) ─────────── */
const STATUS_META: Record<
  RuleStatus,
  { label: string; variant: Parameters<typeof Badge>[0]['variant'] }
> = {
  active: { label: 'Active', variant: 'success' },
  pending_approval: { label: 'Pending approval', variant: 'warning' },
  rejected: { label: 'Rejected', variant: 'destructive' },
  draft: { label: 'Draft', variant: 'muted' },
  disabled: { label: 'Disabled', variant: 'muted' },
}

const TYPE_LABEL: Record<RuleType, string> = {
  threshold: 'Threshold',
  sod: 'Segregation of duties',
  typology: 'Typology',
  velocity: 'Velocity',
}

function RuleStatusBadge({ status }: { status: RuleStatus }) {
  const meta = STATUS_META[status] ?? { label: humanize(status), variant: 'outline' as const }
  return <Badge variant={meta.variant}>{meta.label}</Badge>
}

/** A param value rendered for read-only display (booleans / strings / numbers). */
function paramDisplay(p: RuleParam): string {
  if (typeof p.value === 'boolean') return p.value ? 'On' : 'Off'
  return p.unit ? `${p.value} ${p.unit}` : String(p.value)
}

/* ── A single editable param row ────────────────────────────────────────────── */
function ParamField({
  param,
  draft,
  editable,
  onChange,
}: {
  param: RuleParam
  draft: number | string | boolean
  editable: boolean
  onChange: (next: number | string | boolean) => void
}) {
  const id = `param-${param.key}`
  if (typeof param.value === 'boolean') {
    return (
      <div className="flex items-center justify-between gap-3 rounded-md border border-border/60 bg-muted/20 px-3 py-2">
        <Label htmlFor={id} className="text-xs font-medium">
          {param.label}
        </Label>
        <Button
          id={id}
          type="button"
          size="sm"
          variant={draft ? 'default' : 'outline'}
          disabled={!editable}
          onClick={() => onChange(!draft)}
          aria-pressed={Boolean(draft)}
        >
          {draft ? 'On' : 'Off'}
        </Button>
      </div>
    )
  }
  const isNumber = typeof param.value === 'number'
  return (
    <div className="rounded-md border border-border/60 bg-muted/20 px-3 py-2">
      <Label htmlFor={id} className="text-xs font-medium text-muted-foreground">
        {param.label}
      </Label>
      <div className="mt-1 flex items-center gap-2">
        <Input
          id={id}
          type={isNumber ? 'number' : 'text'}
          inputMode={isNumber ? 'decimal' : 'text'}
          value={String(draft)}
          disabled={!editable}
          className="h-8 tabular-nums"
          onChange={(e) => onChange(isNumber ? Number(e.target.value) : e.target.value)}
        />
        {param.unit ? (
          <span className="shrink-0 text-xs text-muted-foreground">{param.unit}</span>
        ) : null}
      </div>
    </div>
  )
}

/* ── Change-history / diff list for one rule ────────────────────────────────── */
function RuleHistory({ history }: { history: RuleChange[] }) {
  const [historyRef] = useAutoAnimateList<HTMLOListElement>()
  if (history.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">No change history recorded for this rule.</p>
    )
  }
  return (
    <ol ref={historyRef} className="space-y-3">
      {history.map((h, i) => (
        <li key={`${h.version}-${h.ts}`} className="relative pl-5">
          <span
            className={cn(
              'absolute left-0 top-1 size-2.5 rounded-full ring-2 ring-card',
              i === 0 ? 'bg-primary' : 'bg-muted-foreground/50',
            )}
            aria-hidden
          />
          {i < history.length - 1 ? (
            <span
              className="absolute left-[0.3rem] top-4 h-[calc(100%-0.5rem)] w-px bg-border"
              aria-hidden
            />
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-xs font-semibold">v{h.version}</span>
            <RuleStatusBadge status={h.status} />
            <span className="text-xs text-muted-foreground">{formatRelative(h.ts)}</span>
          </div>
          <p className="mt-0.5 text-xs">{h.summary}</p>
          <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
            {h.proposed_by}
            {h.proposed_role ? ` · ${humanize(h.proposed_role)}` : ''} · {formatIST(h.ts)}
            {h.approved_by ? ` · approved by ${h.approved_by}` : ''}
          </p>
          {h.diff && h.diff.length > 0 ? (
            <ul className="mt-1 space-y-0.5">
              {h.diff.map((d) => (
                <li key={d.field} className="flex items-center gap-1.5 font-mono text-[0.7rem]">
                  <span className="text-muted-foreground">{humanize(d.field)}:</span>
                  <span className="text-severity-medium line-through">{String(d.from)}</span>
                  <ChevronRight className="size-3 text-muted-foreground" />
                  <span className="text-sla-ok">{String(d.to)}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ol>
  )
}

/* ── One rule card (read / edit / history) ──────────────────────────────────── */
function RuleCard({
  rule,
  canPropose,
  constraint,
}: {
  rule: Rule
  canPropose: boolean
  constraint?: string
}) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [drafts, setDrafts] = useState<Record<string, number | string | boolean>>(() =>
    Object.fromEntries(rule.params.map((p) => [p.key, p.value])),
  )
  const [summary, setSummary] = useState('')

  const dirty = useMemo(
    () => rule.params.some((p) => drafts[p.key] !== p.value),
    [drafts, rule.params],
  )

  const pendingChange = rule.status === 'pending_approval'

  const update = useMutation({
    mutationFn: () =>
      apiClient.updateRule(rule.id, {
        params: rule.params.map((p) => ({ ...p, value: drafts[p.key] })),
        summary: summary.trim() || `Adjusted ${rule.name} thresholds`,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.rules() })
      toast.success('Change submitted for four-eyes approval', {
        description: 'The rule stays at its current version until a second authoriser approves it.',
      })
      setEditing(false)
      setSummary('')
    },
    onError: (err) =>
      toast.error('Could not submit change', {
        description: err instanceof ApiError ? err.message : 'Unexpected error. Please retry.',
      }),
  })

  function resetDrafts() {
    setDrafts(Object.fromEntries(rule.params.map((p) => [p.key, p.value])))
    setSummary('')
    setEditing(false)
  }

  return (
    <Card className={cn(pendingChange && 'ring-1 ring-inset ring-sla-warn/40')}>
      <CardHeader className="gap-2 pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2">
              <ScrollText className="size-4 shrink-0 text-reason-rule" />
              <span className="truncate">{rule.name}</span>
            </CardTitle>
            <CardDescription className="mt-1">{rule.description}</CardDescription>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            <RuleStatusBadge status={rule.status} />
            <span className="font-mono text-[0.7rem] text-muted-foreground">v{rule.version}</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[0.7rem] text-muted-foreground">
          <Badge variant="outline" className="font-normal">
            {TYPE_LABEL[rule.type] ?? humanize(rule.type)}
          </Badge>
          {rule.code ? <span className="font-mono">{rule.code}</span> : null}
          <span>·</span>
          <span>
            Updated by {rule.updated_by} · {formatRelative(rule.updated_ts)}
          </span>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {pendingChange ? (
          <div className="flex items-start gap-2 rounded-md border border-sla-warn/30 bg-sla-warn/10 px-3 py-2 text-xs text-sla-warn">
            <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
            <span>
              A proposed change to this rule is awaiting a second authoriser. The active version
              stays in force until approval (four-eyes, enforced server-side).
            </span>
          </div>
        ) : null}

        {/* Params */}
        {rule.params.length === 0 ? (
          <p className="text-xs text-muted-foreground">This rule has no tunable parameters.</p>
        ) : editing ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {rule.params.map((p) => (
              <ParamField
                key={p.key}
                param={p}
                draft={drafts[p.key]}
                editable={!update.isPending}
                onChange={(next) => setDrafts((d) => ({ ...d, [p.key]: next }))}
              />
            ))}
          </div>
        ) : (
          <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
            {rule.params.map((p) => (
              <div
                key={p.key}
                className="flex items-center justify-between gap-2 border-b border-border/40 py-1"
              >
                <dt className="text-xs text-muted-foreground">{p.label}</dt>
                <dd className="text-xs font-medium tabular-nums">{paramDisplay(p)}</dd>
              </div>
            ))}
          </dl>
        )}

        {/* Edit form footer */}
        {editing ? (
          <div className="space-y-2 rounded-md border border-border/60 bg-muted/20 p-3">
            <div>
              <Label htmlFor={`summary-${rule.id}`} className="text-xs">
                Change rationale (required for the approver)
              </Label>
              <Input
                id={`summary-${rule.id}`}
                value={summary}
                disabled={update.isPending}
                placeholder="e.g. Raise new-beneficiary high-value threshold to ₹10L per Q2 risk review"
                className="mt-1 h-8"
                onChange={(e) => setSummary(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-center gap-1 text-[0.7rem] text-muted-foreground">
                <Lock className="size-3" />
                Submits as a proposal — never goes live without a second sign-off.
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  disabled={update.isPending}
                  onClick={resetDrafts}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={!dirty || update.isPending}
                  onClick={() => update.mutate()}
                >
                  {update.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <GitCommitVertical className="size-3.5" />
                  )}
                  Submit for approval
                </Button>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>

      <Separator />

      <div className="flex items-center justify-between px-4 py-2">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 gap-1.5 px-2 text-xs text-muted-foreground"
          onClick={() => setShowHistory((v) => !v)}
          aria-expanded={showHistory}
        >
          {showHistory ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronRight className="size-3.5" />
          )}
          <History className="size-3.5" />
          History ({rule.history?.length ?? 0})
        </Button>

        {!editing ? (
          canPropose ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7"
              disabled={pendingChange}
              onClick={() => setEditing(true)}
            >
              <PencilLine className="size-3.5" />
              {constraint ? `Propose change (${constraint})` : 'Propose change'}
            </Button>
          ) : (
            <InfoTip label="Editing rules requires the tune-rules capability. Your role has read-only access here.">
              <span className="flex items-center gap-1 text-[0.7rem] text-muted-foreground">
                <Lock className="size-3" /> Read-only
              </span>
            </InfoTip>
          )
        ) : null}
      </div>

      {showHistory ? (
        <CardContent className="pt-0">
          <RuleHistory history={rule.history ?? []} />
        </CardContent>
      ) : null}
    </Card>
  )
}

function RulesEditorSkeleton() {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-48 w-full" />
      ))}
    </div>
  )
}

/**
 * Rule / threshold editor (FRONTEND-12; blueprint Part 24.4 screen 5, l.956). Lists
 * `apiClient.listRules()` as editable cards. Edits are submitted via `apiClient.updateRule` and routed
 * to **pending approval** (four-eyes, enforced server-side) — never straight to active. Edit controls are
 * gated on `can('tune_rules')`; for cluster_head the matrix constraint is "propose_only".
 */
export function RulesEditor() {
  const { can, constraintFor } = useAuth()
  const canPropose = can('tune_rules')
  const constraint = constraintFor('tune_rules')
  const [gridRef] = useAutoAnimateList<HTMLDivElement>()

  const rulesQuery = useQuery({
    queryKey: queryKeys.rules(),
    queryFn: () => apiClient.listRules(),
  })

  const rules = rulesQuery.data ?? []
  const pendingCount = rules.filter((r) => r.status === 'pending_approval').length

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="size-4 text-primary" />
            Rules &amp; thresholds
          </CardTitle>
          <CardDescription className="mt-1">
            Change-controlled detection rules. Every edit is a proposal that needs a second
            authoriser before it goes live (four-eyes).
          </CardDescription>
        </div>
        {pendingCount > 0 ? (
          <Badge variant="warning" className="shrink-0 tabular-nums">
            {pendingCount} pending approval
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent>
        <QueryBoundary
          isLoading={rulesQuery.isLoading}
          isError={rulesQuery.isError}
          error={rulesQuery.error}
          onRetry={() => void rulesQuery.refetch()}
          skeleton={<RulesEditorSkeleton />}
        >
          {rules.length === 0 ? (
            <EmptyState
              icon={ScrollText}
              title="No rules configured"
              description="Detection rules and thresholds will appear here once published by the rule registry."
            />
          ) : (
            <div ref={gridRef} className="grid gap-3 lg:grid-cols-2">
              {rules.map((rule) => (
                <RuleCard
                  key={rule.id}
                  rule={rule}
                  canPropose={canPropose}
                  constraint={constraint}
                />
              ))}
            </div>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  )
}
