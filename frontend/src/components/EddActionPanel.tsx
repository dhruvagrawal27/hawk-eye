import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowUpRight,
  Ban,
  CheckCircle2,
  HelpCircle,
  Loader2,
  Lock,
  Scale,
  ShieldAlert,
  ShieldQuestion,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError } from '@/lib/http'
import { useAuth } from '@/auth/rbac'
import { violatesSoD } from '@/auth/capabilities'
import { isEventId } from '@/lib/format'
import type {
  Alert,
  BlockRequestResponse,
  DispositionOutcome,
  DispositionResponse,
} from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { InfoTip } from '@/components/ui/tooltip'
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
import { MaskedPII } from '@/components/MaskedPII'
import { StatusBadge } from '@/components/badges'
import { EddChecklist } from '@/components/EddChecklist'
import { AuditConfirmation } from '@/components/AuditConfirmation'

/**
 * EDD action panel + feedback loop (FRONTEND-11; Blueprint Part 11 l.392, Part 24.4 l.954, Part
 * 24.5c, Part 10, natural justice).
 *
 * Golden rules honoured:
 *  - ALERT-ONLY: no auto-block / auto-classify. "Request block" is a *request* routed to a Lead —
 *    it never blocks. Every disposition needs an explicit human click.
 *  - RBAC + SoD: action controls are gated by `useAuth().can(...)` and `violatesSoD(role, cap)`.
 *    Read-only roles (chief_internal_auditor, dgm_compliance, data_science_lead per SoD) never see
 *    mutation controls.
 *  - Proportionality / human-in-the-loop: fraud and escalate require notes *and* ≥1 evidence id.
 *  - Every disposition is written to the immutable audit log AND becomes a label feeding the L3/L4
 *    relabeling loop (Part 10) — surfaced via <AuditConfirmation>.
 */

type ActionKind = 'fraud' | 'false_positive' | 'inconclusive' | 'escalate'

const OUTCOME_FOR: Record<ActionKind, DispositionOutcome> = {
  fraud: 'fraud',
  false_positive: 'false_positive',
  inconclusive: 'inconclusive',
  escalate: 'inconclusive', // escalate is dispositioned inconclusive + routed up via notes
}

const ACTION_META: Record<
  ActionKind,
  { label: string; description: string; icon: typeof CheckCircle2; tone: string }
> = {
  fraud: {
    label: 'Mark fraud',
    description: 'Confirm this alert as fraud. Writes a positive label.',
    icon: ShieldAlert,
    tone: 'text-severity-critical',
  },
  false_positive: {
    label: 'Close as false positive',
    description: 'Disposition as benign. Writes a negative label.',
    icon: CheckCircle2,
    tone: 'text-sla-ok',
  },
  inconclusive: {
    label: 'Mark inconclusive',
    description: 'Insufficient evidence either way. Logged for review.',
    icon: HelpCircle,
    tone: 'text-severity-medium',
  },
  escalate: {
    label: 'Escalate to Lead',
    description: 'Hand to a Team Lead for override / further action.',
    icon: ArrowUpRight,
    tone: 'text-severity-high',
  },
}

/** Outcomes that, by proportionality, require notes + at least one evidence id. */
const REQUIRES_EVIDENCE: ActionKind[] = ['fraud', 'escalate']

const TERMINAL_STATUSES = new Set<Alert['status']>([
  'confirmed_fraud',
  'false_positive',
  'inconclusive',
  'closed',
])

function parseEvidenceIds(raw: string): string[] {
  return Array.from(
    new Set(
      raw
        .split(/[,\s]+/)
        .map((s) => s.trim())
        .filter(Boolean),
    ),
  )
}

export function EddActionPanel({ alert }: { alert: Alert }) {
  const auth = useAuth()
  const role = auth.role
  const qc = useQueryClient()

  const [notes, setNotes] = useState('')
  const [evidenceRaw, setEvidenceRaw] = useState('')
  const [checklist, setChecklist] = useState<Record<string, boolean>>({})
  const [pendingAction, setPendingAction] = useState<ActionKind | null>(null)
  const [dispositionResult, setDispositionResult] = useState<DispositionResponse | null>(null)
  const [blockResult, setBlockResult] = useState<BlockRequestResponse | null>(null)
  const [blockReason, setBlockReason] = useState('')
  const [blockOpen, setBlockOpen] = useState(false)

  const evidenceIds = useMemo(() => parseEvidenceIds(evidenceRaw), [evidenceRaw])
  const malformedEvidence = evidenceIds.filter((id) => !isEventId(id))

  // Capabilities (defense-in-depth; server is authoritative).
  const canDisposition = auth.can('disposition')
  const canRequestBlock = auth.can('request_block')
  const sodDisposition = role ? violatesSoD(role, 'disposition') : null
  const showDisposition = canDisposition && !sodDisposition

  const alreadyDisposed = TERMINAL_STATUSES.has(alert.status)

  const disposition = useMutation({
    mutationFn: async ({ kind }: { kind: ActionKind }) => {
      const outcome = OUTCOME_FOR[kind]
      const trimmedNotes =
        kind === 'escalate' ? `[ESCALATION REQUEST] ${notes.trim()}` : notes.trim()
      // Two writes: the immutable disposition AND the active-learning label (Part 10 relabel loop).
      const res = await apiClient.dispositionAlert(alert.alert_id, {
        outcome,
        notes: trimmedNotes,
        evidence_ids: evidenceIds,
      })
      await apiClient.submitFeedback({
        alert_id: alert.alert_id,
        outcome,
        notes: trimmedNotes,
      })
      return res
    },
    onSuccess: (res) => {
      setDispositionResult(res)
      setPendingAction(null)
      toast.success('Disposition recorded', {
        description: `Audit ${res.audit_id} · label ${res.label_written ? 'written' : 'pending'}`,
      })
      qc.invalidateQueries({ queryKey: queryKeys.alert(alert.alert_id) })
      qc.invalidateQueries({ queryKey: queryKeys.alerts() })
    },
    onError: (err) => {
      setPendingAction(null)
      toast.error('Disposition failed', {
        description: err instanceof ApiError ? err.message : 'Please retry.',
      })
    },
  })

  const blockRequest = useMutation({
    mutationFn: () =>
      apiClient.blockRequest(alert.alert_id, {
        reason: blockReason.trim(),
        notes: notes.trim() || undefined,
      }),
    onSuccess: (res) => {
      setBlockResult(res)
      setBlockOpen(false)
      toast.success('Block request submitted', {
        description: `Routed to Team Lead for approval · ${res.request_id}`,
      })
      qc.invalidateQueries({ queryKey: queryKeys.alert(alert.alert_id) })
    },
    onError: (err) =>
      toast.error('Block request failed', {
        description: err instanceof ApiError ? err.message : 'Please retry.',
      }),
  })

  function requirementError(kind: ActionKind): string | null {
    if (!notes.trim()) return 'Investigation notes are required to record a disposition.'
    if (REQUIRES_EVIDENCE.includes(kind)) {
      if (evidenceIds.length === 0) {
        return 'At least one evidence id is required to mark fraud or escalate (proportionality).'
      }
      if (malformedEvidence.length > 0) {
        return `Evidence ids must look like evt_… (check: ${malformedEvidence.join(', ')}).`
      }
    }
    return null
  }

  function startAction(kind: ActionKind) {
    const err = requirementError(kind)
    if (err) {
      toast.error('Cannot proceed', { description: err })
      return
    }
    setPendingAction(kind)
  }

  function confirmAction() {
    if (!pendingAction) return
    disposition.mutate({ kind: pendingAction })
  }

  // ── Read-only roles: no mutation controls, just the posture note. ─────────
  if (!showDisposition && !canRequestBlock) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Scale className="size-4 text-muted-foreground" />
            Disposition
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ReadOnlyNotice reason={sodDisposition} canDisposition={canDisposition} />
          <NaturalJusticePosture />
        </CardContent>
      </Card>
    )
  }

  const pendingMeta = pendingAction ? ACTION_META[pendingAction] : null

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Scale className="size-4 text-primary" />
            Disposition &amp; EDD
          </CardTitle>
          <StatusBadge status={alert.status} />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Subject — tokenized entity with audited unmask. */}
        <div className="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2 text-sm">
          <span className="text-muted-foreground">Subject</span>
          <MaskedPII value={alert.entity_id} entityId={alert.entity_id} alertId={alert.alert_id} />
        </div>

        {dispositionResult ? (
          <AuditConfirmation
            auditId={dispositionResult.audit_id}
            labelWritten={dispositionResult.label_written}
            feedbackQueued={dispositionResult.feedback_queued_for_retraining}
            title="Disposition recorded — audit + relabel"
          />
        ) : alreadyDisposed ? (
          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            <Lock className="size-3.5 shrink-0" />
            This alert is already dispositioned ({alert.status}). Re-opening is a Lead override.
          </div>
        ) : (
          <>
            <EddChecklist value={checklist} onChange={setChecklist} />

            <Separator />

            {/* Notes — required for any disposition (natural justice: documented reasoning). */}
            <div className="space-y-1.5">
              <Label htmlFor="edd-notes" className="flex items-center gap-1.5">
                Investigation notes
                <span className="text-destructive" aria-hidden>
                  *
                </span>
                <InfoTip label="A human, documented rationale is required for every disposition (natural justice + audit).">
                  <HelpCircle className="size-3.5 text-muted-foreground" />
                </InfoTip>
              </Label>
              <Textarea
                id="edd-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="What you verified, what the evidence shows, and why this disposition is proportionate…"
                rows={3}
                disabled={disposition.isPending}
              />
            </div>

            {/* Evidence ids — comma/space separated → evidence_ids[]. */}
            <div className="space-y-1.5">
              <Label htmlFor="edd-evidence" className="flex items-center gap-1.5">
                Evidence event ids
                <span className="text-xs font-normal text-muted-foreground">
                  (required for fraud / escalate)
                </span>
              </Label>
              <Input
                id="edd-evidence"
                value={evidenceRaw}
                onChange={(e) => setEvidenceRaw(e.target.value)}
                placeholder="evt_8f3a, evt_91bc…"
                disabled={disposition.isPending}
                aria-invalid={malformedEvidence.length > 0}
                className={cn(malformedEvidence.length > 0 && 'border-destructive')}
              />
              {evidenceIds.length > 0 ? (
                <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                  {evidenceIds.map((id) => (
                    <span
                      key={id}
                      className={cn(
                        'tok rounded px-1.5 py-0.5 font-mono',
                        isEventId(id)
                          ? 'bg-secondary text-secondary-foreground'
                          : 'bg-destructive/15 text-destructive',
                      )}
                    >
                      {id}
                    </span>
                  ))}
                </p>
              ) : null}
              {malformedEvidence.length > 0 ? (
                <p className="flex items-center gap-1 text-xs text-destructive">
                  <AlertTriangle className="size-3" />
                  Evidence ids should look like evt_… — check the highlighted ones.
                </p>
              ) : null}
            </div>

            {/* Disposition actions — gated by RBAC + SoD.
                ALERT-ONLY: the human verdict below IS the classification. There is no separate
                classify step and nothing classifies on its own — the investigator's click is the
                label. (Containment is a distinct request; see the section below.) */}
            {showDisposition ? (
              <div className="space-y-1.5">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  <Scale className="size-3.5 text-primary" aria-hidden />
                  Human verdict — this is the classification
                </p>
                <p className="text-2xs text-muted-foreground">
                  Your call — fraud, false-positive, or inconclusive — is the label. Nothing
                  classifies on its own.
                </p>
                <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
                  <ActionButton
                    kind="fraud"
                    variant="destructive"
                    onClick={() => startAction('fraud')}
                    disabled={disposition.isPending}
                  />
                  <ActionButton
                    kind="false_positive"
                    variant="outline"
                    onClick={() => startAction('false_positive')}
                    disabled={disposition.isPending}
                  />
                  <ActionButton
                    kind="inconclusive"
                    variant="outline"
                    onClick={() => startAction('inconclusive')}
                    disabled={disposition.isPending}
                  />
                  <ActionButton
                    kind="escalate"
                    variant="secondary"
                    onClick={() => startAction('escalate')}
                    disabled={disposition.isPending}
                  />
                </div>
              </div>
            ) : (
              <ReadOnlyNotice reason={sodDisposition} canDisposition={canDisposition} />
            )}
          </>
        )}

        {/* Request block — a REQUEST routed to a Lead, never an auto-block. Set apart from the
            disposition above so the verdict-vs-request distinction is unmistakable. */}
        {canRequestBlock ? (
          <div className="rounded-md border border-severity-high/25 bg-severity-high/5 p-3">
            <RequestBlockSection
              open={blockOpen}
              onOpenChange={setBlockOpen}
              reason={blockReason}
              onReasonChange={setBlockReason}
              isPending={blockRequest.isPending}
              onSubmit={() => blockRequest.mutate()}
              result={blockResult}
              entityId={alert.entity_id}
              alertId={alert.alert_id}
            />
          </div>
        ) : null}

        <Separator />
        <NaturalJusticePosture />
      </CardContent>

      {/* Confirmation dialog — the explicit, single human click that records the decision. */}
      <Dialog
        open={pendingAction !== null}
        onOpenChange={(o) => {
          if (!o && !disposition.isPending) setPendingAction(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {pendingMeta ? <pendingMeta.icon className={cn('size-4', pendingMeta.tone)} /> : null}
              {pendingMeta?.label}
            </DialogTitle>
            <DialogDescription>
              You are about to record a disposition for{' '}
              <span className="tok font-mono">{alert.alert_id}</span>. This is written to the
              immutable audit log and becomes a label feeding the L3/L4 relabeling loop (Part 10).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 rounded-md border border-border bg-muted/30 p-3 text-xs">
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Outcome</span>
              <span className="font-medium">{pendingMeta?.label}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Evidence ids</span>
              <span className="font-mono">{evidenceIds.length || '—'}</span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-muted-foreground">Notes</span>
              <span className="whitespace-pre-wrap break-words text-foreground">
                {notes.trim()}
              </span>
            </div>
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button variant="ghost" disabled={disposition.isPending}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              variant={pendingAction === 'fraud' ? 'destructive' : 'default'}
              onClick={confirmAction}
              disabled={disposition.isPending}
            >
              {disposition.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
              Confirm &amp; record
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

/* ── Sub-components ───────────────────────────────────────────────────────── */

function ActionButton({
  kind,
  variant,
  onClick,
  disabled,
}: {
  kind: ActionKind
  variant: 'destructive' | 'outline' | 'secondary' | 'default'
  onClick: () => void
  disabled?: boolean
}) {
  const meta = ACTION_META[kind]
  const Icon = meta.icon
  return (
    <InfoTip label={meta.description}>
      <Button
        type="button"
        variant={variant}
        size="sm"
        className="justify-start"
        onClick={onClick}
        disabled={disabled}
      >
        <Icon className={cn('size-4', variant === 'outline' && meta.tone)} />
        {meta.label}
      </Button>
    </InfoTip>
  )
}

function RequestBlockSection({
  open,
  onOpenChange,
  reason,
  onReasonChange,
  isPending,
  onSubmit,
  result,
  entityId,
  alertId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  reason: string
  onReasonChange: (v: string) => void
  isPending: boolean
  onSubmit: () => void
  result: BlockRequestResponse | null
  entityId: string
  alertId: string
}) {
  return (
    <div className="space-y-2">
      <div className="space-y-0.5">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <ShieldQuestion className="size-3.5 text-severity-high" aria-hidden />
          Containment — a request, not a verdict
        </p>
        <p className="text-2xs text-muted-foreground">
          Separate from the classification above: a block is a request routed to a Team Lead for
          approval. Nothing here blocks on its own.
        </p>
      </div>

      {result ? (
        <div
          className="rounded-md border border-severity-high/30 bg-severity-high/5 p-3 text-xs"
          role="status"
        >
          <p className="flex items-center gap-1.5 font-medium text-severity-high">
            <ShieldQuestion className="size-3.5" />
            Block request pending Team Lead approval
          </p>
          <p className="mt-1 text-muted-foreground">
            Request <span className="tok font-mono">{result.request_id}</span> routed to{' '}
            <span className="font-medium">{result.routed_to_role}</span>. Nothing is blocked until a
            Lead approves · audit {result.audit_id}.
          </p>
        </div>
      ) : (
        <Dialog open={open} onOpenChange={onOpenChange}>
          <div className="flex items-start gap-2 rounded-md border border-dashed border-border p-2.5">
            <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-severity-high" />
            <div className="min-w-0 flex-1">
              <p className="text-xs text-muted-foreground">
                Request a block — this is a{' '}
                <span className="font-medium text-foreground">request</span> routed to a Team Lead
                for approval. It never auto-blocks (alert-only system).
              </p>
              <DialogTrigger asChild>
                <Button type="button" variant="outline" size="sm" className="mt-2">
                  <Ban className="size-4 text-severity-high" />
                  Request block
                </Button>
              </DialogTrigger>
            </div>
          </div>

          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Ban className="size-4 text-severity-high" />
                Request block — routed to Lead
              </DialogTitle>
              <DialogDescription>
                This submits a request for{' '}
                <MaskedPII value={entityId} entityId={entityId} alertId={alertId} /> to a Team Lead.
                It does <span className="font-medium text-foreground">not</span> block anything; a
                Lead must approve.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-1.5">
              <Label htmlFor="block-reason">Reason for the request</Label>
              <Textarea
                id="block-reason"
                value={reason}
                onChange={(e) => onReasonChange(e.target.value)}
                placeholder="Why containment is warranted (active exfiltration, confirmed mule, leaver with access)…"
                rows={3}
                disabled={isPending}
              />
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="ghost" disabled={isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <Button onClick={onSubmit} disabled={isPending || !reason.trim()}>
                {isPending ? <Loader2 className="size-4 animate-spin" /> : null}
                Submit request to Lead
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

function ReadOnlyNotice({
  reason,
  canDisposition,
}: {
  reason: string | null
  canDisposition: boolean
}) {
  // SoD reason (e.g. data_science_lead) takes priority; otherwise a plain capability gap.
  const message =
    reason ??
    (canDisposition
      ? null
      : 'Your role is read-only for case disposition. Decisions are made by investigators.')
  if (!message) return null
  return (
    <div className="flex items-start gap-2 rounded-md border border-severity-medium/30 bg-severity-medium/5 p-2.5 text-xs text-severity-medium">
      <Lock className="mt-0.5 size-3.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

function NaturalJusticePosture() {
  const points = [
    'The model explains, but does not decide — a human dispositions.',
    'Proportionate: fraud / escalation require notes and evidence.',
    'Auditable: every decision is logged immutably and is contestable.',
  ]
  return (
    <div className="space-y-1 rounded-md bg-muted/30 p-2.5 text-xs text-muted-foreground">
      <p className="flex items-center gap-1.5 font-medium text-foreground">
        <Scale className="size-3.5" />
        Natural-justice posture
      </p>
      <ul className="space-y-0.5 pl-5">
        {points.map((p) => (
          <li key={p} className="list-disc">
            {p}
          </li>
        ))}
      </ul>
    </div>
  )
}
