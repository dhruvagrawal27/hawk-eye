/**
 * ApprovalQueue (AGENT B — manager oversight). A four-eyes approval / escalation queue for managers
 * and the fraud-function lead: the alerts that are *waiting on a human above the investigator* —
 * block requests routed up (golden rule #1: a block is a REQUEST, never an auto-action), explicit
 * escalations, and the most severe still-open alerts.
 *
 * Derived entirely from `apiClient.listAlerts` (no new route): an alert lands here when its status is
 * `escalated` / `pending_lead_approval` (block-request routed to a Lead) or when it is high/critical
 * and still open. Inline Approve / Reject are **gated by the RBAC matrix** —
 *   Approve  → can(role, 'request_block')  (the manager confirms the containment request)
 *   Reject   → can(role, 'disposition')    (the manager dispositions it back / benign)
 * — and applied **optimistically** (the row leaves the queue immediately) with a sonner toast and a
 * rollback on error. The server is authoritative; these guards are defense-in-depth.
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  ChevronRight,
  GanttChartSquare,
  Loader2,
  ShieldQuestion,
  SquareArrowOutUpRight,
  X,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import {
  compositePriority,
  formatINRCompact,
  formatRelative,
  featureFriendlyLabel,
} from '@/lib/format'
import type { Alert, Paginated, ReasonCode } from '@/lib/types'
import { useAuth } from '@/auth/rbac'
import { can } from '@/auth/capabilities'
import { cn } from '@/lib/cn'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { RiskBadge } from '@/components/ui/risk-badge'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusBadge } from '@/components/badges'
import { MaskedPII } from '@/components/MaskedPII'
import { EmployeeActivitySummary } from '@/components/EmployeeActivitySummary'
import { toast } from '@/components/ui/toaster'

/** A short label for one reason code (rule code / SHAP feature / graph ring). */
function reasonLabel(rc: ReasonCode): string {
  if (rc.source === 'rule') return rc.code
  if (rc.source === 'shap') return featureFriendlyLabel(rc.feature)
  return rc.ring_id ? `ring ${rc.ring_id}` : 'graph link'
}
/** One reason code as a readable sentence for the expanded "why flagged" list. */
function reasonDetail(rc: ReasonCode): string {
  if (rc.source === 'rule') return `${rc.code} — ${rc.detail}`
  if (rc.source === 'shap') return `${featureFriendlyLabel(rc.feature)} (model feature)`
  return rc.detail
}
/** "L1_rules" → "L1" for a compact layer chip. */
function shortLayer(l: string): string {
  return l.split('_')[0].toUpperCase()
}

/** Statuses that route an alert into the manager queue (block-request routed up / escalated). */
const PENDING_STATUSES = new Set<string>(['escalated', 'pending_lead_approval'])

/** True when an alert is awaiting a manager decision: explicitly routed up, or severe and still open. */
function needsApproval(a: Alert): boolean {
  if (PENDING_STATUSES.has(a.status)) return true
  return (a.severity === 'critical' || a.severity === 'high') && a.status === 'open'
}

/** Why this alert reached the queue — drives the small reason chip. */
function approvalReason(a: Alert): string {
  // `pending_lead_approval` is a runtime status the queue surfaces (block-request routed up) that
  // sits outside the strict AlertStatus union — compare as a string.
  if ((a.status as string) === 'pending_lead_approval') return 'Block request'
  if (a.status === 'escalated') return 'Escalated'
  return 'High severity'
}

type Decision = 'approve' | 'reject'

export function ApprovalQueue() {
  const { role } = useAuth()
  const qc = useQueryClient()

  const canApprove = can(role ?? undefined, 'request_block')
  const canReject = can(role ?? undefined, 'disposition')

  const query = useQuery({
    queryKey: queryKeys.alerts({}),
    queryFn: () => apiClient.listAlerts({}),
  })

  const pending = useMemo(() => {
    const items = (query.data?.items ?? []).filter(needsApproval)
    return items.sort((a, b) => compositePriority(b) - compositePriority(a))
  }, [query.data])

  const decide = useMutation({
    mutationFn: ({ alert, decision }: { alert: Alert; decision: Decision }) =>
      apiClient.dispositionAlert(alert.alert_id, {
        // Approve confirms the routed request (fraud); reject sends it back as benign.
        outcome: decision === 'approve' ? 'fraud' : 'false_positive',
        notes:
          decision === 'approve'
            ? `[APPROVED] Escalation/block request approved via manager oversight queue (${approvalReason(alert)}).`
            : '[REJECTED] Returned from manager oversight queue — no containment warranted.',
        evidence_ids: [],
      }),
    // Optimistic: drop the row from the cached queue immediately.
    onMutate: async ({ alert, decision }) => {
      await qc.cancelQueries({ queryKey: queryKeys.alerts({}) })
      const previous = qc.getQueryData<Paginated<Alert>>(queryKeys.alerts({}))
      qc.setQueryData<Paginated<Alert>>(queryKeys.alerts({}), (old) =>
        old
          ? {
              ...old,
              items: old.items.map((a) =>
                a.alert_id === alert.alert_id
                  ? { ...a, status: decision === 'approve' ? 'confirmed_fraud' : 'false_positive' }
                  : a,
              ),
            }
          : old,
      )
      return { previous, decision }
    },
    onError: (err, _vars, ctx) => {
      if (ctx?.previous) qc.setQueryData(queryKeys.alerts({}), ctx.previous)
      toast.error('Decision failed', {
        description: err instanceof ApiError ? err.message : 'Please retry.',
      })
    },
    onSuccess: (res, { decision }) => {
      toast.success(decision === 'approve' ? 'Request approved' : 'Request rejected', {
        description: `Audit ${res.audit_id} · label ${res.label_written ? 'written' : 'pending'}`,
      })
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: queryKeys.alerts() })
    },
  })

  const decidingId = decide.isPending ? decide.variables?.alert.alert_id : undefined

  return (
    <Surface tone="actionable" pad="none" className="overflow-hidden">
      <header className="flex items-start justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <ShieldQuestion className="size-4 text-primary" aria-hidden />
            <Eyebrow>Approval &amp; escalation queue</Eyebrow>
          </div>
          <p className="mt-0.5 text-2xs text-muted-foreground">
            Block requests, escalations and severe open alerts awaiting your decision. Expand a row
            to see why it fired and the person&apos;s history before you approve or reject.
          </p>
        </div>
        <Badge variant="secondary" className="shrink-0 font-mono tabular-nums">
          {pending.length} pending
        </Badge>
      </header>

      <div className="p-3">
        <QueryBoundary
          isLoading={query.isLoading}
          isError={query.isError}
          error={query.error}
          onRetry={() => query.refetch()}
        >
          {pending.length === 0 ? (
            <EmptyState
              icon={GanttChartSquare}
              title="Nothing awaiting approval"
              description="Block requests, escalations and severe open alerts surface here for a manager decision."
            />
          ) : (
            <ul className="space-y-1.5">
              {pending.map((alert) => (
                <ApprovalRow
                  key={alert.alert_id}
                  alert={alert}
                  reason={approvalReason(alert)}
                  canApprove={canApprove}
                  canReject={canReject}
                  deciding={decidingId === alert.alert_id}
                  busy={decide.isPending}
                  onApprove={() => decide.mutate({ alert, decision: 'approve' })}
                  onReject={() => decide.mutate({ alert, decision: 'reject' })}
                />
              ))}
            </ul>
          )}
        </QueryBoundary>
      </div>

      {!canApprove && !canReject ? (
        <p className="border-t border-border px-4 py-2 text-2xs text-muted-foreground">
          Your role can view the oversight queue but cannot approve or reject — those are reserved
          for roles holding request-block / disposition rights.
        </p>
      ) : null}
    </Surface>
  )
}

/** One queue row: headline context inline, with an expandable "why flagged + who is this person". */
function ApprovalRow({
  alert,
  reason,
  canApprove,
  canReject,
  deciding,
  busy,
  onApprove,
  onReject,
}: {
  alert: Alert
  reason: string
  canApprove: boolean
  canReject: boolean
  deciding: boolean
  busy: boolean
  onApprove: () => void
  onReject: () => void
}) {
  const [open, setOpen] = useState(false)
  const codes = alert.reason_codes ?? []
  const layers = alert.contributing_layers ?? []

  return (
    <li className="rounded-md border border-border bg-card/60">
      <div className="flex items-center gap-3 px-3 py-2">
        <button
          type="button"
          className="focus-ring -m-1 shrink-0 rounded p-1 text-muted-foreground hover:text-foreground"
          aria-expanded={open}
          aria-label={open ? 'Hide details' : 'Show why it fired'}
          onClick={() => setOpen((o) => !o)}
        >
          <ChevronRight className={cn('size-4 transition-transform', open && 'rotate-90')} />
        </button>
        <RiskBadge score={alert.risk_score} size="md" className="shrink-0" />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">
              {alert.title ?? 'Alert pending review'}
            </span>
            <Badge variant="outline" className="shrink-0 text-2xs uppercase">
              {reason}
            </Badge>
          </div>
          {/* Inline "why flagged" — top signals + layers + confidence, straight from the alert (no fetch). */}
          {codes.length > 0 || layers.length > 0 ? (
            <div className="mt-1 flex flex-wrap items-center gap-1">
              {codes.slice(0, 2).map((rc, i) => (
                <Badge key={i} variant="secondary" className="max-w-[16rem] truncate text-3xs">
                  {reasonLabel(rc)}
                </Badge>
              ))}
              {codes.length > 2 ? (
                <Badge variant="secondary" className="text-3xs">
                  +{codes.length - 2}
                </Badge>
              ) : null}
              {layers.length > 0 ? (
                <span className="font-mono text-3xs text-muted-foreground">
                  {layers.map((l) => shortLayer(String(l))).join('·')}
                </span>
              ) : null}
              <span className="text-3xs text-muted-foreground">
                · {Math.round(alert.confidence * 100)}% confidence
              </span>
            </div>
          ) : null}
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-2xs text-muted-foreground">
            <MaskedPII
              value={alert.entity_id}
              entityId={alert.entity_id}
              alertId={alert.alert_id}
            />
            <span className="text-muted-foreground/50">·</span>
            <span className="tabular-nums">{formatINRCompact(alert.exposure_inr)}</span>
            <span className="text-muted-foreground/50">·</span>
            <StatusBadge status={alert.status} className="px-1.5 py-0 text-2xs" />
            <span className="text-muted-foreground/50">·</span>
            <span title={alert.created_ts}>{formatRelative(alert.created_ts)}</span>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {canApprove ? (
            <Button
              type="button"
              size="sm"
              className="h-7 gap-1 px-2"
              disabled={busy}
              onClick={onApprove}
            >
              {deciding ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Check className="size-3.5" />
              )}
              Approve
            </Button>
          ) : null}
          {canReject ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1 px-2"
              disabled={busy}
              onClick={onReject}
            >
              <X className="size-3.5" />
              Reject
            </Button>
          ) : null}
          {!canApprove && !canReject ? (
            <span className="text-2xs text-muted-foreground">Read-only</span>
          ) : null}
        </div>
      </div>

      {open ? (
        <div className="space-y-3 border-t border-border/60 px-3 py-2.5">
          {/* Why flagged — the full reason codes */}
          {codes.length > 0 ? (
            <div className="text-2xs">
              <p className="mb-1 font-medium uppercase tracking-wide text-muted-foreground">
                Why it fired
              </p>
              <ul className="list-disc space-y-0.5 pl-4 text-foreground/85">
                {codes.map((rc, i) => (
                  <li key={i}>{reasonDetail(rc)}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Who is this person — history before you decide */}
          <EmployeeActivitySummary entityId={alert.entity_id} enabled={open} />

          <Link
            to={`/alerts/${alert.alert_id}`}
            className="inline-flex items-center gap-1 text-2xs font-medium text-primary hover:underline"
          >
            <SquareArrowOutUpRight className="size-3" /> Open full alert &amp; explanation
          </Link>
        </div>
      ) : null}
    </li>
  )
}
