/**
 * Feature / score drift chart (FRONTEND-13; blueprint Part 24.4 screen 7).
 *
 * One small-multiple line per `DriftSeries`: the metric value over time against its alert threshold
 * (rendered as a dashed reference line). The series status (ok / warning / drifting) drives both the
 * line colour and a status badge, so a model engineer can spot a drifting feature at a glance — the
 * trigger to investigate a retrain. De-identified, aggregate statistics only (no case PII).
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { Activity, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatISTDate, humanize } from '@/lib/format'
import { EmptyState } from '@/components/ui/empty-state'
import type { DriftSeries, DriftStatus } from '@/lib/types'

const STATUS_META: Record<DriftStatus, { label: string; stroke: string; badge: string }> = {
  ok: { label: 'OK', stroke: 'hsl(var(--sla-ok))', badge: 'text-sla-ok bg-sla-ok/12' },
  warning: {
    label: 'Warning',
    stroke: 'hsl(var(--sla-warn))',
    badge: 'text-sla-warn bg-sla-warn/12',
  },
  drifting: {
    label: 'Drifting',
    stroke: 'hsl(var(--severity-critical))',
    badge: 'text-severity-critical bg-severity-critical/12',
  },
}

const METRIC_LABEL: Record<DriftSeries['metric'], string> = {
  psi: 'PSI',
  ks: 'KS statistic',
  js: 'JS divergence',
}

interface ChartPoint {
  ts: string
  date: string
  value: number
  threshold?: number
}

function DriftTooltip({
  active,
  payload,
  metricLabel,
}: Partial<TooltipContentProps<number, string>> & { metricLabel: string }) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload as ChartPoint
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      <div className="font-medium text-popover-foreground">{point.date}</div>
      <div className="mt-0.5 flex items-center gap-2 tabular-nums">
        <span className="text-muted-foreground">{metricLabel}</span>
        <span className="font-medium text-foreground">{point.value.toFixed(3)}</span>
      </div>
      {point.threshold != null ? (
        <div className="tabular-nums text-muted-foreground">
          threshold <span className="text-foreground">{point.threshold.toFixed(3)}</span>
        </div>
      ) : null}
    </div>
  )
}

function SeriesPanel({ series }: { series: DriftSeries }) {
  const meta = STATUS_META[series.status]
  const metricLabel = METRIC_LABEL[series.metric]
  const data: ChartPoint[] = series.points.map((p) => ({
    ts: p.ts,
    date: formatISTDate(p.ts),
    value: p.value,
    threshold: p.threshold,
  }))
  const threshold = series.points.find((p) => p.threshold != null)?.threshold

  return (
    <div className="rounded-lg border border-border bg-background/40 p-3">
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {series.feature ? humanize(series.feature) : 'Score distribution'}
          </p>
          <p className="text-[0.7rem] text-muted-foreground">
            <span className="font-mono">{series.model_id}</span> · {metricLabel}
          </p>
        </div>
        <span
          className={cn(
            'inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[0.7rem] font-semibold',
            meta.badge,
          )}
        >
          <Activity className="size-3" />
          {meta.label}
        </span>
      </div>
      <div className="h-40 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              minTickGap={24}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={false}
              width={42}
              domain={[0, 'auto']}
            />
            <RTooltip content={<DriftTooltip metricLabel={metricLabel} />} />
            {threshold != null ? (
              <ReferenceLine
                y={threshold}
                stroke="hsl(var(--severity-high))"
                strokeDasharray="4 4"
                strokeWidth={1.25}
                label={{
                  value: `threshold ${threshold}`,
                  fontSize: 10,
                  fill: 'hsl(var(--severity-high))',
                  position: 'insideTopRight',
                }}
              />
            ) : null}
            <Line
              type="monotone"
              dataKey="value"
              stroke={meta.stroke}
              strokeWidth={2}
              dot={{ r: 2, fill: meta.stroke }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function DriftChart({ series }: { series: DriftSeries[] }) {
  if (series.length === 0) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No drift series"
        description="No population-stability or distribution-shift series are being tracked right now."
      />
    )
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {series.map((s) => (
        <SeriesPanel key={`${s.model_id}:${s.feature ?? s.metric}`} series={s} />
      ))}
    </div>
  )
}
