import { Hash, IndianRupee, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIST, formatINR, humanize } from '@/lib/format'
import type { Alert } from '@/lib/types'
import { MaskedPII } from '@/components/MaskedPII'
import { SlaTimer } from '@/components/SlaTimer'
import {
  ConfidenceMeter,
  ContributingLayers,
  PiiTokenizedBadge,
  RiskScore,
  SeverityBadge,
  StatusBadge,
} from '@/components/badges'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'

/**
 * Alert/case header (Part 24.4 screen 3 header) — the at-a-glance risk posture an investigator reads
 * first: calibrated risk score, severity, model confidence, status, SLA/TAT countdown, the tokenized
 * entity, and the contributing detection layers (L1–L6). Money in INR, time in IST.
 *
 * This is a header, not a decision surface — the disposition/EDD controls live in the action rail.
 */
export function AlertHeader({ alert }: { alert: Alert }) {
  const title = alert.title ?? humanize(alert.alert_type ?? 'Suspicious activity alert')

  return (
    <Card className="overflow-hidden">
      {/* Top band: score + identity + live SLA */}
      <div className="flex flex-wrap items-start gap-4 p-4">
        <RiskScore score={alert.risk_score} size="lg" />

        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="truncate text-base font-semibold tracking-tight">{title}</h2>
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
              Raised <span className="text-foreground">{formatIST(alert.created_ts)}</span>
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          <SlaTimer dueTs={alert.sla_due_ts} showDate className="text-sm" />
          <ConfidenceMeter confidence={alert.confidence} />
        </div>
      </div>

      <Separator />

      {/* Lower band: exposure + detection layers */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <Metric icon={<IndianRupee className="size-3.5" />} label="Exposure at risk">
            <span className="text-sm font-semibold tabular-nums text-foreground">
              {formatINR(alert.exposure_inr)}
            </span>
          </Metric>
          <Metric icon={<ShieldAlert className="size-3.5" />} label="Detection layers">
            {alert.contributing_layers.length > 0 ? (
              <ContributingLayers layers={alert.contributing_layers} />
            ) : (
              <span className="text-muted-foreground">—</span>
            )}
          </Metric>
        </div>
      </div>
    </Card>
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
        <span className="text-[0.65rem] uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <div className="flex items-center">{children}</div>
      </div>
    </div>
  )
}
