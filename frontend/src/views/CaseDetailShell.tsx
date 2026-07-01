import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  Briefcase,
  CheckCircle2,
  ChevronRight,
  Flag,
  History,
  Loader2,
  MessagesSquare,
  Siren,
  UserCog,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { formatINRCompact, formatIST, statusLabel } from '@/lib/format'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/rbac'
import { violatesSoD, rolesWithCapability, ROLE_META } from '@/auth/capabilities'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { MaskedPII } from '@/components/MaskedPII'
import { SlaTimer } from '@/components/SlaTimer'
import { CaseNotes } from '@/components/CaseNotes'
import { CaseHistory } from '@/components/CaseHistory'
import { CaseDossier, ExportDossierButton } from '@/components/CaseDossier'
import { RiskScore, SeverityBadge, StatusBadge, ContributingLayers } from '@/components/badges'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { toast } from '@/components/ui/toaster'
import { Eyebrow } from '@/components/ui/eyebrow'
import { AmountFlip, RouteTransition, SlaRing } from '@/ui'
import type { Alert, CaseDetail, CaseStatus } from '@/lib/types'

/** Linear case workflow (Part 24.4 screen 4): open → in_progress → escalated → closed. */
const WORKFLOW: CaseStatus[] = ['open', 'in_progress', 'escalated', 'closed']

/** Short labels of the roles that may triage/assign cases — surfaced to read-only roles so a blocked
 *  user knows who *does* own the action (per docs/BANK_ROLES.md capability matrix). */
const TRIAGE_OWNERS = rolesWithCapability('triage')
  .map((r) => ROLE_META[r].short)
  .join(', ')

const STATUS_META: Record<CaseStatus, { icon: typeof Flag; verb: string }> = {
  open: { icon: Briefcase, verb: 'Reopen' },
  in_progress: { icon: ArrowRight, verb: 'Start investigation' },
  escalated: { icon: Flag, verb: 'Escalate' },
  closed: { icon: CheckCircle2, verb: 'Close case' },
}

export function CaseDetailShell() {
  const { caseId = '' } = useParams<{ caseId: string }>()
  const navigate = useNavigate()

  const caseQuery = useQuery({
    queryKey: queryKeys.case(caseId),
    queryFn: () => apiClient.getCase(caseId),
    enabled: Boolean(caseId),
  })

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<Briefcase className="size-5" />}
        title={
          <span className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate('/cases')}
              className="text-muted-foreground hover:text-foreground focus-ring"
              aria-label="Back to cases"
            >
              <ArrowLeft className="size-4" />
            </button>
            {caseQuery.data?.title ?? 'Case'}
          </span>
        }
        description={<span className="font-mono text-xs text-muted-foreground">{caseId}</span>}
        actions={caseQuery.data ? <ExportDossierButton /> : null}
      />

      <QueryBoundary
        isLoading={caseQuery.isLoading}
        isError={caseQuery.isError}
        error={caseQuery.error}
        onRetry={() => void caseQuery.refetch()}
        skeleton={
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <Skeleton className="h-96 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        }
      >
        {caseQuery.data ? <CaseDetailBody detail={caseQuery.data} /> : null}
      </QueryBoundary>
    </RouteTransition>
  )
}

function CaseDetailBody({ detail }: { detail: CaseDetail }) {
  const exposure =
    detail.exposure_inr ?? detail.alerts.reduce((sum, a) => sum + (a.exposure_inr ?? 0), 0)

  return (
    <>
      <CaseDossier detail={detail} />
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_22rem] print:hidden">
        <div className="space-y-4">
          <LinkedAlertsPanel alerts={detail.alerts} />

          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle className="flex items-center gap-1.5">
                <MessagesSquare className="size-4 text-muted-foreground" /> Notes
                <Badge variant="muted" className="ml-1">
                  {detail.notes.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CaseNotes caseId={detail.case_id} notes={detail.notes} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <History className="size-4 text-muted-foreground" /> Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CaseHistory history={detail.history} />
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-4">
          <CaseSummaryCard detail={detail} exposure={exposure} />
          <WorkflowCard detail={detail} />
          <AssignmentCard detail={detail} />
        </aside>
      </div>
    </>
  )
}

/* ── Linked alerts ──────────────────────────────────────────────────────── */

function LinkedAlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-1.5">
          <Siren className="size-4 text-muted-foreground" /> Linked alerts
          <Badge variant="muted" className="ml-1">
            {alerts.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <EmptyState
            icon={Siren}
            title="No alerts linked"
            description="This case has no alerts associated with it."
          />
        ) : (
          <ul className="divide-y divide-border">
            {alerts.map((alert) => (
              <li key={alert.alert_id}>
                <Link
                  to={`/alerts/${alert.alert_id}`}
                  className="-mx-2 flex items-center gap-3 rounded-md px-2 py-2.5 transition-colors hover:bg-muted/40 focus-ring"
                >
                  <RiskScore score={alert.risk_score} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate text-sm font-medium">
                        {alert.title ?? alert.alert_type ?? alert.alert_id}
                      </span>
                      <SeverityBadge severity={alert.severity} />
                      <StatusBadge status={alert.status} />
                    </div>
                    <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.7rem] text-muted-foreground">
                      <span className="font-mono">{alert.alert_id}</span>
                      <span>·</span>
                      <span className="inline-flex items-center gap-1">
                        Entity{' '}
                        <span onClick={(e) => e.preventDefault()}>
                          <MaskedPII
                            value={alert.entity_id}
                            entityId={alert.entity_id}
                            alertId={alert.alert_id}
                          />
                        </span>
                      </span>
                      <span>·</span>
                      <span className="font-mono tabular-nums">
                        {formatINRCompact(alert.exposure_inr)}
                      </span>
                      <ContributingLayers layers={alert.contributing_layers} className="ml-1" />
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <SlaTimer dueTs={alert.sla_due_ts} compact />
                    <ChevronRight className="size-4 text-muted-foreground" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

/* ── Summary ────────────────────────────────────────────────────────────── */

function CaseSummaryCard({ detail, exposure }: { detail: CaseDetail; exposure: number }) {
  return (
    <Card>
      <CardHeader className="space-y-1">
        <Eyebrow>Dossier</Eyebrow>
        <CardTitle className="font-display">Case summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2.5 text-sm">
        <Row label="Status">
          <StatusBadge status={detail.status} />
        </Row>
        <Row label="Severity">
          <SeverityBadge severity={detail.severity} />
        </Row>
        <Row label="Entity">
          <MaskedPII value={detail.entity_id} entityId={detail.entity_id} />
        </Row>
        <Row label="Alerts">
          <span className="tabular-nums">{detail.alert_ids.length}</span>
        </Row>
        <Row label="Exposure">
          <AmountFlip value={exposure} kind="inr" className="text-sm font-medium text-foreground" />
        </Row>
        {detail.sla_due_ts ? (
          <Row label="SLA">
            <div className="flex items-center gap-2">
              <SlaTimer dueTs={detail.sla_due_ts} compact showDate />
              <SlaRing dueTs={detail.sla_due_ts} size={30} showLabel={false} />
            </div>
          </Row>
        ) : null}
        <Separator />
        <Row label="Opened">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatIST(detail.created_ts)}
          </span>
        </Row>
        <Row label="Updated">
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {formatIST(detail.updated_ts)}
          </span>
        </Row>
      </CardContent>
    </Card>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}

/* ── Workflow (explicit human status transitions; alert-only) ───────────── */

function WorkflowCard({ detail }: { detail: CaseDetail }) {
  const { can, role } = useAuth()
  const queryClient = useQueryClient()
  const canTriage = can('triage')
  const sod = role ? violatesSoD(role, 'triage') : null

  const [target, setTarget] = useState<CaseStatus | null>(null)
  const [note, setNote] = useState('')

  const updateStatus = useMutation({
    mutationFn: (next: CaseStatus) =>
      apiClient.updateCaseStatus(detail.case_id, { status: next, note: note.trim() || undefined }),
    onSuccess: (_data, next) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.case(detail.case_id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.cases() })
      setTarget(null)
      setNote('')
      toast.success(`Case moved to ${statusLabel(next)}`)
    },
    onError: (err) =>
      toast.error('Status change failed', {
        description: err instanceof ApiError ? err.message : undefined,
      }),
  })

  const transitions = useMemo(() => WORKFLOW.filter((s) => s !== detail.status), [detail.status])
  const currentIndex = WORKFLOW.indexOf(detail.status)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">Workflow</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ol className="flex items-center justify-between">
          {WORKFLOW.map((s, i) => {
            const done = i < currentIndex
            const active = i === currentIndex
            return (
              <li key={s} className="flex flex-1 flex-col items-center gap-1 text-center">
                <span
                  className={cn(
                    'flex size-6 items-center justify-center rounded-full text-[0.65rem] font-semibold ring-1 ring-inset',
                    active && 'bg-primary text-primary-foreground ring-primary',
                    done && 'bg-primary/20 text-primary ring-primary/40',
                    !active && !done && 'bg-muted text-muted-foreground ring-border',
                  )}
                >
                  {i + 1}
                </span>
                <span
                  className={cn(
                    'text-[0.62rem] leading-tight',
                    active ? 'font-medium text-foreground' : 'text-muted-foreground',
                  )}
                >
                  {statusLabel(s)}
                </span>
              </li>
            )
          })}
        </ol>

        <Separator />

        {!canTriage || sod ? (
          <p className="rounded-md bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground">
            {sod ??
              `Your role — ${role ? ROLE_META[role].label : 'this role'} — has read-only access to case workflow. Status transitions are performed by the case-handling roles: ${TRIAGE_OWNERS}.`}
          </p>
        ) : (
          <Dialog
            open={target !== null}
            onOpenChange={(open) => {
              if (!open) {
                setTarget(null)
                setNote('')
              }
            }}
          >
            <div className="flex flex-wrap gap-2">
              {transitions.map((s) => {
                const Icon = STATUS_META[s].icon
                return (
                  <DialogTrigger asChild key={s}>
                    <Button
                      variant={
                        s === 'closed' ? 'default' : s === 'escalated' ? 'destructive' : 'outline'
                      }
                      size="sm"
                      onClick={() => setTarget(s)}
                    >
                      <Icon />
                      {STATUS_META[s].verb}
                    </Button>
                  </DialogTrigger>
                )
              })}
            </div>

            <DialogContent>
              <DialogHeader>
                <DialogTitle>
                  {target ? STATUS_META[target].verb : 'Change status'} · {detail.case_id}
                </DialogTitle>
                <DialogDescription>
                  This is an explicit human action and is recorded in the case audit trail. Changing
                  a case status never auto-blocks or auto-classifies any alert.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-1.5">
                <Label htmlFor="status-note">Note (optional)</Label>
                <Input
                  id="status-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={`Why move to ${target ? statusLabel(target) : 'this status'}?`}
                />
                <p className="text-[0.7rem] text-muted-foreground">
                  Moving from{' '}
                  <span className="font-medium text-foreground">{statusLabel(detail.status)}</span>{' '}
                  to{' '}
                  <span className="font-medium text-foreground">
                    {target ? statusLabel(target) : '—'}
                  </span>
                  .
                </p>
              </div>

              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" size="sm" disabled={updateStatus.isPending}>
                    Cancel
                  </Button>
                </DialogClose>
                <Button
                  size="sm"
                  variant={target === 'escalated' ? 'destructive' : 'default'}
                  disabled={!target || updateStatus.isPending}
                  onClick={() => target && updateStatus.mutate(target)}
                >
                  {updateStatus.isPending ? <Loader2 className="animate-spin" /> : null}
                  Confirm
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </CardContent>
    </Card>
  )
}

/* ── Assignment ─────────────────────────────────────────────────────────── */

function AssignmentCard({ detail }: { detail: CaseDetail }) {
  const { can, user, role } = useAuth()
  const queryClient = useQueryClient()
  const canTriage = can('triage')
  const [assignee, setAssignee] = useState('')

  const assign = useMutation({
    mutationFn: (next: string) => apiClient.assignCase(detail.case_id, { assignee: next }),
    onSuccess: (_data, next) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.case(detail.case_id) })
      void queryClient.invalidateQueries({ queryKey: queryKeys.cases() })
      setAssignee('')
      toast.success(`Case assigned to ${next}`)
    },
    onError: (err) =>
      toast.error('Assignment failed', {
        description: err instanceof ApiError ? err.message : undefined,
      }),
  })

  const self = user?.username ?? user?.name ?? ''

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          <UserCog className="size-4 text-muted-foreground" /> Assignment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Row label="Current">
          {detail.assignee ? (
            <span className="font-medium">{detail.assignee}</span>
          ) : (
            <span className="text-muted-foreground">Unassigned</span>
          )}
        </Row>

        {canTriage ? (
          <Tabs defaultValue="self">
            <TabsList className="w-full">
              <TabsTrigger value="self" className="flex-1">
                Assign to me
              </TabsTrigger>
              <TabsTrigger value="other" className="flex-1">
                Reassign
              </TabsTrigger>
            </TabsList>
            <TabsContent value="self" className="mt-3">
              <Button
                size="sm"
                className="w-full"
                disabled={!self || assign.isPending || detail.assignee === self}
                onClick={() => self && assign.mutate(self)}
              >
                {assign.isPending ? <Loader2 className="animate-spin" /> : <UserCog />}
                {detail.assignee === self ? 'Already yours' : `Assign to ${self || 'me'}`}
              </Button>
            </TabsContent>
            <TabsContent value="other" className="mt-3 space-y-2">
              <div className="space-y-1.5">
                <Label htmlFor="assignee">Assignee</Label>
                <Input
                  id="assignee"
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                  placeholder="username or investigator id"
                />
              </div>
              <Button
                size="sm"
                className="w-full"
                disabled={!assignee.trim() || assign.isPending}
                onClick={() => assign.mutate(assignee.trim())}
              >
                {assign.isPending ? <Loader2 className="animate-spin" /> : null}
                Reassign case
              </Button>
            </TabsContent>
          </Tabs>
        ) : (
          <p className="rounded-md bg-muted/40 px-2.5 py-2 text-xs text-muted-foreground">
            Your role — {role ? ROLE_META[role].label : 'this role'} — cannot assign cases. Assignment
            is handled by the case-handling roles: {TRIAGE_OWNERS}.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
