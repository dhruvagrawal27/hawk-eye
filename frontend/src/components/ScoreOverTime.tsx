/**
 * Score-over-time — a 0–100 fused-risk-score history for an entity (Blueprint Part 11 / Part 24.4).
 * It answers "how did this entity's risk evolve into the alert?" so a reviewer can see whether the
 * score crept up over weeks or spiked in a single off-hours burst.
 *
 * A Recharts step AreaChart over the score series, with severity ReferenceArea bands (low / medium /
 * high / critical) painted behind it so the band a point sits in is read by colour, not by squinting
 * at the axis. Animation is disabled (isAnimationActive=false) to match the rest of the console and
 * keep it deterministic for snapshot/contract tests.
 */
import { useQuery } from '@tanstack/react-query'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { LineChart as LineChartIcon } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatISTDate, formatIST } from '@/lib/format'
import { riskColor, riskLevelFromScore, RISK_TEXT } from '@/lib/risk'
import { cn } from '@/lib/cn'
import { QueryBoundary } from '@/components/QueryBoundary'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import type { ScoreHistoryPoint } from '@/lib/types'

/** Severity bands on the 0–100 axis (mirrors riskLevelFromScore cut-points). */
const BANDS: { from: number; to: number; varName: string }[] = [
  { from: 0, to: 40, varName: '--severity-low' },
  { from: 40, to: 70, varName: '--severity-medium' },
  { from: 70, to: 85, varName: '--severity-high' },
  { from: 85, to: 100, varName: '--severity-critical' },
]

interface ChartPoint {
  ts: string
  date: string
  score: number
  note?: string
}

function ScoreTooltip({ active, payload }: Partial<TooltipContentProps<number, string>>) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload as ChartPoint
  const level = riskLevelFromScore(point.score)
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      <div className="font-medium text-popover-foreground">{formatIST(point.ts)}</div>
      <div className="mt-0.5 flex items-center gap-2 tabular-nums">
        <span className="text-muted-foreground">risk</span>
        <span className={cn('font-semibold', RISK_TEXT[level])}>{Math.round(point.score)}</span>
      </div>
      {point.note ? <div className="mt-0.5 text-muted-foreground">{point.note}</div> : null}
    </div>
  )
}

function Chart({
  points,
  thresholdScore,
}: {
  points: ScoreHistoryPoint[]
  thresholdScore?: number
}) {
  if (points.length === 0) {
    return (
      <EmptyState
        icon={LineChartIcon}
        title="No score history"
        description="No fused-risk-score history has been recorded for this entity yet."
      />
    )
  }

  const data: ChartPoint[] = points.map((p) => ({
    ts: p.ts,
    date: formatISTDate(p.ts),
    score: p.score,
    note: p.note,
  }))
  const latest = data[data.length - 1]?.score ?? 0
  const latestLevel = riskLevelFromScore(latest)

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Risk score over time
        </p>
        <span className="flex items-baseline gap-1 text-xs text-muted-foreground">
          latest
          <span className={cn('text-sm font-bold tabular-nums', RISK_TEXT[latestLevel])}>
            {Math.round(latest)}
          </span>
        </span>
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 6, right: 10, bottom: 0, left: -20 }}>
            <defs>
              <linearGradient id="score-over-time-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={riskColor(latest)} stopOpacity={0.35} />
                <stop offset="100%" stopColor={riskColor(latest)} stopOpacity={0.02} />
              </linearGradient>
            </defs>

            {/* Severity bands painted behind the series so the band is read by colour. */}
            {BANDS.map((b) => (
              <ReferenceArea
                key={b.varName}
                y1={b.from}
                y2={b.to}
                fill={`hsl(var(${b.varName}))`}
                fillOpacity={0.06}
                ifOverflow="hidden"
                stroke="none"
              />
            ))}

            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              minTickGap={24}
            />
            <YAxis
              domain={[0, 100]}
              ticks={[0, 40, 70, 85, 100]}
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              tickLine={false}
              axisLine={false}
              width={42}
            />
            <RTooltip content={<ScoreTooltip />} />
            {thresholdScore != null ? (
              <ReferenceLine
                y={thresholdScore}
                stroke="hsl(var(--foreground))"
                strokeDasharray="4 4"
                strokeWidth={1}
                strokeOpacity={0.6}
                label={{
                  value: `threshold ${Math.round(thresholdScore)}`,
                  fontSize: 10,
                  fill: 'hsl(var(--muted-foreground))',
                  position: 'insideTopLeft',
                }}
              />
            ) : null}
            <Area
              type="step"
              dataKey="score"
              stroke={riskColor(latest)}
              strokeWidth={2}
              fill="url(#score-over-time-fill)"
              dot={{ r: 2, fill: riskColor(latest), strokeWidth: 0 }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export function ScoreOverTime({ entityId }: { entityId: string }) {
  const query = useQuery({
    queryKey: queryKeys.scoreHistory(entityId),
    queryFn: () => apiClient.getScoreHistory(entityId),
    enabled: entityId.length > 0,
  })

  return (
    <QueryBoundary
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      skeleton={<Skeleton className="h-48 w-full rounded-lg" />}
    >
      {query.data ? (
        <Chart points={query.data.points} thresholdScore={query.data.threshold_score} />
      ) : (
        <EmptyState
          icon={LineChartIcon}
          title="No score history"
          description="No fused-risk-score history has been recorded for this entity yet."
        />
      )}
    </QueryBoundary>
  )
}
