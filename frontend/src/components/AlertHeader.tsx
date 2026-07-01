import { AlertTriangle, GitBranch, Hash, IndianRupee, ShieldAlert, Sigma } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIST, humanize } from '@/lib/format'
import type { Alert, ReasonCode } from '@/lib/types'
import { MaskedPII } from '@/components/MaskedPII'
import {
  ContributingLayers,
  PiiTokenizedBadge,
  SeverityBadge,
  StatusBadge,
} from '@/components/badges'
import { Card } from '@/components/ui/card'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Separator } from '@/components/ui/separator'
import { AmountFlip, RiskGauge, SlaRing } from '@/ui'

/**
 * Alert/case header (Part 24.4 screen 3 header) — the at-a-glance risk posture an investigator reads
 * first: calibrated risk score (with a confidence ring), severity, status, SLA/TAT countdown, the
 * tokenized entity, the ₹ exposure roll-up, and — non-negotiably — a **reason-code preview**. Money in
 * INR, time in IST, evidence in mono.
 *
 * CONTESTABILITY (invariant #2): every alert view renders its reason codes. If this alert carries none,
 * the header surfaces an explicit "no reason codes — alert invalid" state, never a blank. This is a
 * header, not a decision surface — disposition/EDD controls live in the action rail; nothing here acts.
 */
export function AlertHeader({ alert }: { alert: Alert }) {
  const title = alert.title ?? humanize(alert.alert_type ?? 'Suspicious activity alert')

  return (
    <Card className="overflow-hidden shadow-dossier">
      {/* Top band: score + identity + live SLA */}
      <div className="flex flex-wrap items-start gap-5 p-4 sm:p-5">
        <RiskGauge
          score={alert.risk_score}
          confidence={alert.confidence}
          size="lg"
          label="risk"
          className="shrink-0"
        />

        <div className="min-w-0 flex-1 space-y-2">
          <Eyebrow>Alert dossier</Eyebrow>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-display text-xl font-semibold leading-tight tracking-tight text-foreground">
              {title}
            </h2>
            <SeverityBadge severity={alert.severity} />
            <StatusBadge status={alert.status} />
            {alert.pii_tokenized ? <PiiTokenizedBadge /> : null}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1 font-mono tabular-nums">
              <Hash className="size-3.5" />
              {alert.alert_id}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground/80">Entity</span>
              <MaskedPII
                value={alert.entity_id}
                entityId={alert.entity_id}
                alertId={alert.alert_id}
                className="font-medium text-foreground"
              />
            </span>
            <span>
              Raised{' '}
              <span className="font-mono tabular-nums text-foreground">
                {formatIST(alert.created_ts)}
              </span>
            </span>
            <span className="inline-flex items-center gap-1">
              <Sigma className="size-3.5" />
              Confidence{' '}
              <span className="font-mono tabular-nums text-foreground">
                {Math.round(alert.confidence * 100)}%
              </span>
            </span>
          </div>

          <ReasonCodeStrip codes={alert.reason_codes} />
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <SlaRing dueTs={alert.sla_due_ts} size={52} />
        </div>
      </div>

      <Separator />

      {/* Lower band: exposure + detection layers */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2 text-xs">
          <Metric icon={<IndianRupee className="size-3.5" />} label="Exposure at risk">
            <AmountFlip
              value={alert.exposure_inr}
              kind="inr"
              className="text-base font-semibold text-foreground"
            />
          </Metric>
          <Metric icon={<ShieldAlert className="size-3.5" />} label="Detection layers">
            {alert.contributing_layers.length > 0 ? (
              <ContributingLayers layers={alert.contributing_layers} />
            ) : (
              <span className="font-mono text-muted-foreground">—</span>
            )}
          </Metric>
        </div>
      </div>
    </Card>
  )
}

/* ── Reason-code preview — contestability made visible at the top of the case file ─────────────── */

const REASON_META: Record<
  ReasonCode['source'],
  { label: string; className: string; icon: typeof Hash }
> = {
  rule: {
    label: 'Rule',
    className: 'text-reason-rule ring-reason-rule/30 bg-reason-rule/5',
    icon: ShieldAlert,
  },
  shap: {
    label: 'SHAP',
    className: 'text-reason-shap ring-reason-shap/30 bg-reason-shap/5',
    icon: Sigma,
  },
  graph: {
    label: 'Graph',
    className: 'text-reason-graph ring-reason-graph/30 bg-reason-graph/5',
    icon: GitBranch,
  },
}

function reasonText(code: ReasonCode): string {
  if (code.source === 'rule') return code.code
  if (code.source === 'shap') return code.feature
  return code.detail
}

/**
 * Compact, always-present reason-code strip. A valid alert shows up to three of its top reasons (full
 * provenance lives in the Explanation panel). An alert with **no** reason codes is invalid — we say so
 * explicitly (never a blank), because an unexplained alert cannot be contested.
 */
function ReasonCodeStrip({ codes }: { codes: ReasonCode[] }) {
  if (!codes || codes.length === 0) {
    return (
      <div
        role="status"
        className="mt-1 inline-flex items-center gap-2 rounded-md border border-severity-high/40 bg-severity-high/10 px-2.5 py-1.5 text-xs font-medium text-severity-high"
      >
        <AlertTriangle className="size-3.5" />
        No reason codes — alert invalid. An alert that cannot be explained cannot be actioned.
      </div>
    )
  }

  const shown = codes.slice(0, 3)
  const extra = codes.length - shown.length

  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <span className="text-2xs uppercase tracking-widest text-muted-foreground">Why</span>
      {shown.map((code, i) => {
        const meta = REASON_META[code.source]
        const Icon = meta.icon
        return (
          <span
            key={i}
            className={cn(
              'inline-flex max-w-[16rem] items-center gap-1 truncate rounded-md px-2 py-0.5 font-mono text-2xs ring-1 ring-inset',
              meta.className,
            )}
            title={`${meta.label}: ${reasonText(code)}`}
          >
            <Icon className="size-3 shrink-0" />
            <span className="truncate">{reasonText(code)}</span>
          </span>
        )
      })}
      {extra > 0 ? (
        <span className="text-2xs tabular-nums text-muted-foreground">+{extra} more →</span>
      ) : null}
    </div>
  )
}

function Metric({
  icon,
  label,
  children,
  className,
}: {
  icon: React.ReactNode
  label: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-muted-foreground">{icon}</span>
      <div className="flex flex-col gap-0.5">
        <span className="text-2xs uppercase tracking-widest text-muted-foreground">{label}</span>
        <div className="flex items-center">{children}</div>
      </div>
    </div>
  )
}
