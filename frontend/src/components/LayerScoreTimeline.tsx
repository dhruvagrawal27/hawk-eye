/**
 * Per-layer score timeline — one line per detection layer over time (mirrors ClickHouse
 * `hawkeye.scores`). Where ScoreOverTime shows the single fused line, this decomposes it: you can
 * see L3 (GBDT) leading early, L5 (graph) staying flat then jumping late as the ring resolves, and
 * L6 fusion riding on top — with the alert emit line (70) as a reference. Answers "which layer saw
 * it first, and which one pushed it over?" across time, not just at the moment of the alert.
 */
import { useQuery } from '@tanstack/react-query'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { LineChart as LineIcon } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { formatISTDate } from '@/lib/format'
import { LAYER_INFO } from '@/lib/layerFusion'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Skeleton } from '@/components/ui/skeleton'
import type { LayerScoresResponse } from '@/lib/types'

function colorFor(layer: string): string {
  const accent = LAYER_INFO[layer]?.accentVar ?? 'var(--muted-foreground)'
  return `hsl(${accent})`
}

function Chart({ data }: { data: LayerScoresResponse }) {
  const series = data.series
  // The backend names each series (e.g. "Fused L6"); prefer that over the generic layer label.
  const labelByLayer = Object.fromEntries(series.map((s) => [s.layer, s.label || s.layer]))
  const labelFor = (layer: string): string => labelByLayer[layer] ?? LAYER_INFO[layer]?.label ?? layer
  const len = series[0]?.points.length ?? 0
  // zip the aligned per-layer points into one row per time index for a shared X axis
  const rows = Array.from({ length: len }, (_, i) => {
    const row: Record<string, number | string> = {
      idx: i,
      ts: series[0]?.points[i]?.ts ?? '',
    }
    for (const s of series) row[s.layer] = s.points[i]?.score ?? 0
    return row
  })

  return (
    <div>
      <p className="mb-1.5 text-2xs leading-relaxed text-muted-foreground">
        Each line is one detection layer’s score (0–100) over time. The{' '}
        <span className="font-semibold text-foreground">bold line</span> is the fused L6 score; the{' '}
        <span className="text-severity-high">dashed bar</span> is the emit threshold (
        {data.threshold_score}). Read left → right: which layer rises first, and which one carries the
        fused score across the bar.
      </p>
      <div style={{ height: 220 }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 6, right: 12, bottom: 4, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.4} />
            <XAxis
              dataKey="ts"
              tickFormatter={(ts: string) => formatISTDate(ts).slice(0, 6)}
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={24}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
              axisLine={false}
              tickLine={false}
              width={32}
            />
            <RTooltip
              contentStyle={{
                background: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(ts) => formatISTDate(String(ts))}
              formatter={(value, name) => [value as number, labelFor(String(name))]}
            />
            <ReferenceLine
              y={data.threshold_score}
              stroke="hsl(var(--severity-high))"
              strokeDasharray="4 4"
              strokeOpacity={0.7}
              label={{
                value: `emit ${data.threshold_score}`,
                position: 'right',
                fontSize: 9,
                fill: 'hsl(var(--severity-high))',
              }}
            />
            {series.map((s) => (
              <Line
                key={s.layer}
                type="monotone"
                dataKey={s.layer}
                name={s.layer}
                stroke={colorFor(s.layer)}
                strokeWidth={s.layer === 'L6_fusion' ? 2.5 : 1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {/* legend — with each layer's latest score so it's readable without hovering */}
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
        {series.map((s) => {
          const last = s.points[s.points.length - 1]?.score
          return (
            <span
              key={s.layer}
              className="inline-flex items-center gap-1 text-2xs text-muted-foreground"
            >
              <span
                className="h-0.5 w-3 rounded-full"
                style={{ backgroundColor: colorFor(s.layer) }}
                aria-hidden
              />
              {labelFor(s.layer)}
              {last != null ? (
                <span className="tabular-nums font-medium text-foreground/70">{Math.round(last)}</span>
              ) : null}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export function LayerScoreTimeline({
  entityId,
  className,
}: {
  entityId: string
  className?: string
}) {
  const query = useQuery({
    queryKey: queryKeys.layerScores(entityId),
    queryFn: () => apiClient.getLayerScores(entityId),
  })
  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <Eyebrow className="flex items-center gap-1.5">
        <LineIcon className="size-3" />
        Per-layer score timeline · which layer saw it first
      </Eyebrow>
      <QueryBoundary
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        skeleton={<Skeleton className="h-56 w-full" />}
      >
        {query.data ? <Chart data={query.data} /> : null}
      </QueryBoundary>
    </Surface>
  )
}
