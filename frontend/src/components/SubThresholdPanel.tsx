/**
 * Sub-threshold ('hidden 95%') panel — the detection funnel + near-miss watchlist.
 *
 * Every event runs the full stack, but only fused ≥ 70 becomes an alert; everything below is
 * scored-then-dropped. This panel makes that silent majority visible: the funnel (scored →
 * sub-threshold → alerted) and a watchlist of elevated-but-not-alerted entities (40–69) — the
 * slow-drift actors and near-misses the alert queue never shows. Read-only; it never creates alerts.
 */
import { useQuery } from '@tanstack/react-query'
import { Layers, Moon, TrendingDown } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { formatISTTime, formatISTDate, humanize } from '@/lib/format'
import { riskColor } from '@/lib/risk'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Skeleton } from '@/components/ui/skeleton'
import type { SubThresholdResponse } from '@/lib/types'

const nf = new Intl.NumberFormat('en-IN')

/** Band presentation, keyed by the backend band label. */
const BAND_META: Record<string, { label: string; color: string }> = {
  watch: { label: 'Watch · 55–69', color: 'var(--severity-medium)' },
  elevated: { label: 'Elevated · 40–54', color: 'var(--severity-low)' },
  low: { label: 'Low · 0–39', color: 'var(--muted-foreground)' },
}

function FunnelStage({
  label,
  count,
  total,
  color,
  hint,
}: {
  label: string
  count: number
  total: number
  color: string
  hint?: string
}) {
  const pct = total > 0 ? (count / total) * 100 : 0
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums text-muted-foreground">
          <span className="text-foreground">{nf.format(count)}</span>
          {hint ? <span className="ml-1.5 text-2xs">{hint}</span> : null}
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-[width]"
          style={{ width: `${Math.max(1.5, pct)}%`, backgroundColor: `hsl(${color})` }}
        />
      </div>
    </div>
  )
}

function PanelBody({ data }: { data: SubThresholdResponse }) {
  const alertedPct = data.total_scored > 0 ? (data.alerted / data.total_scored) * 100 : 0
  return (
    <div className="space-y-4">
      {/* Detection funnel */}
      <div className="space-y-2.5">
        <FunnelStage
          label="Scored by the full stack"
          count={data.total_scored}
          total={data.total_scored}
          color="var(--primary)"
        />
        <FunnelStage
          label={`Sub-threshold (< ${data.emit_threshold}) — recorded, not alerted`}
          count={data.sub_threshold}
          total={data.total_scored}
          color="var(--severity-medium)"
          hint={`${Math.round((data.sub_threshold / Math.max(1, data.total_scored)) * 100)}%`}
        />
        <FunnelStage
          label="Surfaced as alerts"
          count={data.alerted}
          total={data.total_scored}
          color="var(--severity-high)"
          hint={`${alertedPct.toFixed(alertedPct < 1 ? 2 : 0)}%`}
        />
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-severity-medium/30 bg-severity-medium/10 px-3 py-2 text-xs text-severity-medium">
        <TrendingDown className="mt-0.5 size-4 shrink-0" />
        <p className="leading-relaxed text-foreground/85">
          Only <span className="font-mono tabular-nums">{alertedPct.toFixed(alertedPct < 1 ? 2 : 0)}%</span>{' '}
          of scored activity clears the {data.emit_threshold} bar. The{' '}
          <span className="font-medium">{nf.format(data.sub_threshold)}</span> below it are the
          near-misses and slow-drift actors this watchlist keeps in view.
        </p>
      </div>

      {/* Band breakdown */}
      <div className="space-y-1.5">
        <Eyebrow>Sub-threshold bands</Eyebrow>
        {data.bands.map((b) => {
          const meta = BAND_META[b.label] ?? { label: humanize(b.label), color: 'var(--muted-foreground)' }
          const pct = data.sub_threshold > 0 ? (b.count / data.sub_threshold) * 100 : 0
          return (
            <div key={b.label} className="flex items-center gap-2 text-xs">
              <span className="w-28 shrink-0 text-muted-foreground">{meta.label}</span>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.max(1, pct)}%`, backgroundColor: `hsl(${meta.color})` }}
                />
              </div>
              <span className="w-14 shrink-0 text-right tabular-nums text-foreground">
                {nf.format(b.count)}
              </span>
            </div>
          )
        })}
      </div>

      {/* Near-miss watchlist */}
      {data.watchlist.length > 0 ? (
        <div className="space-y-1.5">
          <Eyebrow>Near-miss watchlist · elevated, not alerted</Eyebrow>
          <ul className="divide-y divide-border/60 rounded-lg border border-border/60">
            {data.watchlist.map((w) => (
              <li key={w.entity_id} className="flex items-center gap-3 px-3 py-1.5 text-xs">
                <span
                  className="w-8 shrink-0 text-center font-mono font-semibold tabular-nums"
                  style={{ color: riskColor(w.score) }}
                >
                  {w.score}
                </span>
                <span className="w-24 shrink-0 truncate font-mono text-foreground">
                  {w.entity_id}
                </span>
                <span className="flex-1 truncate text-muted-foreground">
                  {humanize(w.top_signal)}
                </span>
                <span className="shrink-0 text-2xs tabular-nums text-muted-foreground">
                  {formatISTDate(w.ts)} {formatISTTime(w.ts)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export function SubThresholdPanel({ className }: { className?: string }) {
  const query = useQuery({
    queryKey: queryKeys.subThreshold(),
    queryFn: () => apiClient.getSubThreshold(),
  })

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <Eyebrow className="flex items-center gap-1.5">
          <Layers className="size-3" />
          Ambient activity · the hidden 95%
        </Eyebrow>
        <Moon className="size-3.5 text-muted-foreground" aria-hidden />
      </div>
      <QueryBoundary
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        skeleton={<Skeleton className="h-40 w-full" />}
      >
        {query.data ? <PanelBody data={query.data} /> : null}
      </QueryBoundary>
    </Surface>
  )
}
