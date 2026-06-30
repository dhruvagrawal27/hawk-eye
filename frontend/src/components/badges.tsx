/**
 * Shared domain badges — one visual language for severity, risk score, confidence, status,
 * contributing layers, reason-code provenance (rule·shap·graph), the TEE/AI labels (Part 25) and
 * the actor flags (off-hours / privileged / leaver). Every view imports these so the console reads
 * consistently.
 */
import {
  Brain,
  GitBranch,
  Moon,
  KeyRound,
  LogOut,
  ScrollText,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Lock,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { Badge } from '@/components/ui/badge'
import { layerLabel, statusLabel, formatPercent, type SlaState } from '@/lib/format'
import type { AlertStatus, ContributingLayer, ReasonCodeSource, Severity } from '@/lib/types'

/* ── Severity ───────────────────────────────────────────────────────────── */
const severityClass: Record<Severity, string> = {
  critical: 'text-severity-critical bg-severity-critical/15 ring-severity-critical/30',
  high: 'text-severity-high bg-severity-high/15 ring-severity-high/30',
  medium: 'text-severity-medium bg-severity-medium/15 ring-severity-medium/30',
  low: 'text-severity-low bg-severity-low/15 ring-severity-low/30',
}

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ring-1 ring-inset',
        severityClass[severity],
        className,
      )}
    >
      <span className="size-1.5 rounded-full bg-current" aria-hidden />
      {severity}
    </span>
  )
}

/* ── Risk score (0–100) ─────────────────────────────────────────────────── */
export function RiskScore({
  score,
  size = 'md',
  className,
}: {
  score: number
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const band: Severity =
    score >= 85 ? 'critical' : score >= 65 ? 'high' : score >= 40 ? 'medium' : 'low'
  const dims =
    size === 'lg' ? 'size-14 text-xl' : size === 'sm' ? 'size-8 text-xs' : 'size-11 text-base'
  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-center rounded-full font-bold tabular-nums ring-2 ring-inset',
        severityClass[band],
        dims,
        className,
      )}
      title={`Risk score ${score}/100`}
    >
      {Math.round(score)}
    </div>
  )
}

/* ── Confidence (0–1) ───────────────────────────────────────────────────── */
export function ConfidenceMeter({
  confidence,
  className,
}: {
  confidence: number
  className?: string
}) {
  const pct = Math.round(confidence * 100)
  return (
    <div
      className={cn('flex items-center gap-1.5', className)}
      title={`Model confidence ${confidence}`}
    >
      <div className="h-1.5 w-12 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {formatPercent(confidence)}
      </span>
    </div>
  )
}

/* ── Status ─────────────────────────────────────────────────────────────── */
const statusVariant: Record<string, Parameters<typeof Badge>[0]['variant']> = {
  open: 'default',
  assigned: 'secondary',
  in_progress: 'secondary',
  escalated: 'warning',
  confirmed_fraud: 'destructive',
  false_positive: 'muted',
  inconclusive: 'muted',
  closed: 'muted',
}
export function StatusBadge({
  status,
  className,
}: {
  status: AlertStatus | string
  className?: string
}) {
  return (
    <Badge variant={statusVariant[status] ?? 'outline'} className={cn('uppercase', className)}>
      {statusLabel(status)}
    </Badge>
  )
}

/* ── Contributing layers (L1–L6) ────────────────────────────────────────── */
export function ContributingLayers({
  layers,
  className,
}: {
  layers: (ContributingLayer | string)[]
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap gap-1', className)}>
      {layers.map((l) => (
        <span
          key={l}
          className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.7rem] text-secondary-foreground"
          title={layerLabel(l)}
        >
          {String(l).split('_')[0].toUpperCase()}
        </span>
      ))}
    </div>
  )
}

/* ── Reason-code source ─────────────────────────────────────────────────── */
const reasonMeta: Record<
  ReasonCodeSource,
  { label: string; icon: typeof ScrollText; className: string }
> = {
  rule: { label: 'Rule', icon: ScrollText, className: 'text-reason-rule bg-reason-rule/12' },
  shap: { label: 'SHAP', icon: Brain, className: 'text-reason-shap bg-reason-shap/12' },
  graph: { label: 'Graph', icon: GitBranch, className: 'text-reason-graph bg-reason-graph/12' },
}
export function ReasonSourceBadge({
  source,
  className,
}: {
  source: ReasonCodeSource
  className?: string
}) {
  const meta = reasonMeta[source]
  const Icon = meta.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.7rem] font-medium',
        meta.className,
        className,
      )}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  )
}

/* ── TEE / AI provenance (Part 25) ──────────────────────────────────────── */
export function TeeAttestedBadge({
  attested,
  className,
}: {
  attested: boolean
  className?: string
}) {
  return attested ? (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-tee/15 px-2 py-0.5 text-xs font-medium text-tee',
        className,
      )}
      title="Generated inside a TEE; per-request attestation verified and stored for audit (Part 25)."
    >
      <ShieldCheck className="size-3.5" /> TEE-attested
    </span>
  ) : (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-severity-medium/15 px-2 py-0.5 text-xs font-medium text-severity-medium',
        className,
      )}
      title="Not TEE-attested — a deliberate, logged degradation (Groq / deterministic template). PII still tokenized."
    >
      <ShieldAlert className="size-3.5" /> Not TEE-attested
    </span>
  )
}

export function AiGeneratedBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-ai/15 px-2 py-0.5 text-xs font-medium text-ai',
        className,
      )}
      title="This text is AI-generated narrative (Part 25). The score and decision come from L1–L6; the LLM only explains."
    >
      <Sparkles className="size-3.5" /> AI-generated
    </span>
  )
}

export function PiiTokenizedBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground',
        className,
      )}
      title="PII is tokenized by default (Part 25.3). Unmask is a separate, audited action."
    >
      <Lock className="size-3" /> Tokenized
    </span>
  )
}

/* ── Actor flags ────────────────────────────────────────────────────────── */
export function OffHoursFlag({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1 text-xs text-severity-medium', className)}
      title="Off-hours activity"
    >
      <Moon className="size-3.5" /> Off-hours
    </span>
  )
}
export function PrivilegedFlag({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1 text-xs text-severity-high', className)}
      title="Privileged account"
    >
      <KeyRound className="size-3.5" /> Privileged
    </span>
  )
}
export function LeaverFlag({ className }: { className?: string }) {
  return (
    <span
      className={cn('inline-flex items-center gap-1 text-xs text-severity-critical', className)}
      title="Leaver / resigning"
    >
      <LogOut className="size-3.5" /> Leaver
    </span>
  )
}

/* ── SLA state → tailwind text/bg class (shared by SlaTimer & rows) ─────── */
export const slaStateClass: Record<SlaState, string> = {
  ok: 'text-sla-ok',
  warn: 'text-sla-warn',
  urgent: 'text-sla-urgent',
  breached: 'text-sla-breached',
}
