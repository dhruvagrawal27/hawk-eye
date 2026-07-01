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
import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, GanttChartSquare, Loader2, ShieldQuestion, X } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { compositePriority, formatRelative } from '@/lib/format'
import type { Alert, Paginated } from '@/lib/types'
import { useAuth } from '@/auth/rbac'
import { can } from '@/auth/capabilities'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { RiskBadge } from '@/components/ui/risk-badge'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { StatusBadge } from '@/components/badges'
import { MaskedPII } from '@/components/MaskedPII'
import { toast } from '@/components/ui/toaster'
import { AmountFlip, useAutoAnimateList } from '@/ui'

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

  // AutoAnimate rows out as they clear the queue (optimistic approve/reject) — reduced-motion → instant.
  const [listRef] = useAutoAnimateList<HTMLUListElement>()

  return (
    <Surface tone="actionable" pad="none" className="overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <ShieldQuestion className="size-4 text-primary" aria-hidden />
          <Eyebrow>Approval &amp; escalation queue</Eyebrow>
        </div>
        <Badge variant="secondary" className="font-mono tabular-nums">
          {pending.length} pending
        </Badge>
      </header>

      <div className="p-3">
        {/* Four-eyes posture: the investigator raised the request; a Team Lead makes the second-set-of-
            -eyes decision here. Approving confirms the disposition — it does not block on its own. */}
        <p className="mb-2.5 flex items-start gap-1.5 rounded-md bg-muted/30 px-2.5 py-1.5 text-2xs text-muted-foreground">
          <ShieldQuestion className="mt-px size-3.5 shrink-0 text-primary" aria-hidden />
          <span>
            Four-eyes review — the investigator raised each request; a{' '}
            <span className="font-medium text-foreground">Team Lead</span> approves or rejects here.
            Approving records the disposition; nothing blocks on its own.
          </span>
        </p>
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
            <ul ref={listRef} className="space-y-1.5">
              {pending.map((alert) => (
                <li
                  key={alert.alert_id}
                  className="flex items-center gap-3 rounded-md border border-border bg-card/60 px-3 py-2"
                >
                  <RiskBadge score={alert.risk_score} size="md" className="shrink-0" />

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {alert.title ?? 'Alert pending review'}
                      </span>
                      <Badge variant="outline" className="shrink-0 text-2xs uppercase">
                        {approvalReason(alert)}
                      </Badge>
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-2xs text-muted-foreground">
                      <MaskedPII
                        value={alert.entity_id}
                        entityId={alert.entity_id}
                        alertId={alert.alert_id}
                      />
                      <span className="text-muted-foreground/50">·</span>
                      <AmountFlip
                        value={alert.exposure_inr}
                        kind="inr"
                        compact
                        className="text-2xs text-muted-foreground"
                      />
                      <span className="text-muted-foreground/50">·</span>
                      <StatusBadge status={alert.status} className="px-1.5 py-0 text-2xs" />
                      <span className="text-muted-foreground/50">·</span>
                      <span className="font-mono tabular-nums" title={alert.created_ts}>
                        {formatRelative(alert.created_ts)}
                      </span>
                    </div>
                  </div>

                  <div className="flex shrink-0 items-center gap-1.5">
                    {canApprove ? (
                      <Button
                        type="button"
                        size="sm"
                        className="h-7 gap-1 px-2"
                        disabled={decide.isPending}
                        onClick={() => decide.mutate({ alert, decision: 'approve' })}
                      >
                        {decidingId === alert.alert_id ? (
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
                        disabled={decide.isPending}
                        onClick={() => decide.mutate({ alert, decision: 'reject' })}
                      >
                        <X className="size-3.5" />
                        Reject
                      </Button>
                    ) : null}
                    {!canApprove && !canReject ? (
                      <span className="text-2xs text-muted-foreground">Read-only</span>
                    ) : null}
                  </div>
                </li>
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
