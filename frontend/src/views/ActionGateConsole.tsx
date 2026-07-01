/**
 * L6.5 — Privileged-Action Interdiction console (M3.4).
 *
 * The approver surface for the action-gate: the HOLD_FOR_REVIEW queue (four-eyes approve/reject with
 * mandatory justification, no self-review) + the read-only policy list. ALERT-ONLY: approving a hold
 * only PERMITS human-initiated execution — nothing auto-executes, and the gate never touches money.
 */
import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ShieldAlert, ScaleIcon, Check, X, ListChecks, ChevronDown, History } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { ApiError } from '@/lib/http'
import { cn } from '@/lib/cn'
import type { ActionHold } from '@/lib/types'
import { useAuth } from '@/auth/rbac'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Eyebrow } from '@/components/ui/eyebrow'
import { EmptyState } from '@/components/ui/empty-state'
import { EmployeeActivitySummary } from '@/components/EmployeeActivitySummary'
import { toast } from '@/components/ui/toaster'

export function ActionGateConsole() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const holdsQuery = useQuery({ queryKey: ['action-gate', 'holds'], queryFn: apiClient.listActionHolds })
  const policiesQuery = useQuery({
    queryKey: ['action-gate', 'policies'],
    queryFn: apiClient.listActionPolicies,
  })

  const decide = useMutation({
    mutationFn: ({ holdId, approve, justification }: { holdId: string; approve: boolean; justification: string }) =>
      apiClient.decideActionHold(holdId, {
        decider: user?.username ?? 'me',
        approve,
        justification,
      }),
    onSuccess: (h) => {
      toast.success(h.status === 'approved_via_four_eyes' ? 'Hold approved' : 'Hold rejected', {
        description:
          h.status === 'approved_via_four_eyes'
            ? 'Permitted for human-initiated execution — nothing was auto-run.'
            : 'The held action was denied.',
      })
      void qc.invalidateQueries({ queryKey: ['action-gate', 'holds'] })
    },
    onError: (err) =>
      toast.error('Decision failed', {
        description:
          err instanceof ApiError
            ? err.message
            : 'Could not record the decision (four-eyes: you may not resolve your own hold).',
      }),
  })

  function act(hold: ActionHold, approve: boolean) {
    const justification = window.prompt(
      `${approve ? 'Approve' : 'Reject'} hold for ${hold.subject} (${hold.verb}).\nJustification (audited):`,
      '',
    )?.trim()
    if (!justification) return
    decide.mutate({ holdId: hold.hold_id, approve, justification })
  }

  const holds = useMemo(() => holdsQuery.data?.items ?? [], [holdsQuery.data])

  return (
    <div className="space-y-4">
      <PageHeader
        title="Privileged-action interdiction (L6.5)"
        description="Second-approver review of held staff actions. Alert-only — approving PERMITS human-initiated execution; the gate never auto-executes and never blocks money."
        icon={<ShieldAlert className="size-5" />}
      />

      <QueryBoundary
        isLoading={holdsQuery.isLoading}
        isError={holdsQuery.isError}
        error={holdsQuery.error}
        onRetry={() => void holdsQuery.refetch()}
      >
        {holds.length === 0 ? (
          <EmptyState
            icon={ListChecks}
            title="No actions awaiting review"
            description="Privileged staff actions that trip a hard-gate policy appear here for four-eyes review."
          />
        ) : (
          <div className="space-y-3">
            {holds.map((h) => (
              <HeldActionCard
                key={h.hold_id}
                hold={h}
                busy={decide.isPending}
                onApprove={() => act(h, true)}
                onReject={() => act(h, false)}
              />
            ))}
          </div>
        )}
      </QueryBoundary>

      {/* Policy store (read-only view; edits are a four-eyes change-controlled flow). */}
      <Card>
        <CardContent className="space-y-2 p-4">
          <Eyebrow className="flex items-center gap-1.5">
            <ScaleIcon className="size-3" /> Interdiction policies
          </Eyebrow>
          <div className="divide-y divide-border/60">
            {(policiesQuery.data ?? []).map((p) => (
              <div key={p.code} className="flex items-center gap-2 py-1.5 text-xs">
                <Badge variant={p.gate === 'hard' ? 'destructive' : 'secondary'} className="text-2xs">
                  {p.gate === 'hard' ? 'HOLD' : 'STEP-UP'}
                </Badge>
                <span className="font-medium">{p.name}</span>
                <span className="ml-auto font-mono text-2xs text-muted-foreground">{p.code}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

/** One held privileged action: the request + a collapsible activity log so a senior approver sees
 * what this employee has been doing (and who has already looked) before permitting execution. */
function HeldActionCard({
  hold,
  busy,
  onApprove,
  onReject,
}: {
  hold: ActionHold
  busy: boolean
  onApprove: () => void
  onReject: () => void
}) {
  const [showHistory, setShowHistory] = useState(false)
  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="destructive" className="uppercase">
            {hold.severity}
          </Badge>
          <span className="font-mono text-sm text-foreground">{hold.subject}</span>
          <span className="text-xs text-muted-foreground">·</span>
          <span className="font-mono text-xs text-muted-foreground">{hold.verb}</span>
          {hold.dpia_binding ? (
            <Badge variant="muted" className="ml-auto text-2xs">
              DPIA-bound · natural justice
            </Badge>
          ) : null}
        </div>
        <p className="text-sm text-muted-foreground">{hold.explanation}</p>
        <div className="flex flex-wrap gap-1.5">
          {hold.reason_codes.map((rc) => (
            <Badge key={rc.code} variant="secondary" className="text-2xs">
              {rc.code}
            </Badge>
          ))}
        </div>
        <p className="text-2xs text-muted-foreground">{hold.proportionality}</p>

        {/* Activity log — context on this employee before you permit the action. */}
        <div className="border-t border-border/50 pt-2">
          <button
            type="button"
            className="focus-ring flex w-full items-center justify-between rounded text-2xs font-medium uppercase tracking-wide text-muted-foreground hover:text-foreground"
            aria-expanded={showHistory}
            onClick={() => setShowHistory((s) => !s)}
          >
            <span className="flex items-center gap-1.5">
              <History className="size-3" /> Activity history for {hold.subject}
            </span>
            <ChevronDown className={cn('size-3.5 transition-transform', showHistory && 'rotate-180')} />
          </button>
          {showHistory ? (
            <EmployeeActivitySummary entityId={hold.subject} enabled={showHistory} className="mt-2" />
          ) : null}
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="default" disabled={busy} onClick={onApprove}>
            <Check className="size-3.5" /> Approve (permit)
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={onReject}>
            <X className="size-3.5" /> Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
