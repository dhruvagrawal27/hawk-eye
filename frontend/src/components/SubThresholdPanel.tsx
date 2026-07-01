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
import { formatISTTime, formatISTDate, humanize, featureFriendlyLabel } from '@/lib/format'
import { riskColor } from '@/lib/risk'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Skeleton } from '@/components/ui/skeleton'
import type { SubThresholdResponse } from '@/lib/types'

const nf = new Intl.NumberFormat('en-IN')

/** Band presentation, keyed by the backend band label — plain-English for stakeholders. */
const BAND_META: Record<string, { label: string; color: string }> = {
  watch: { label: 'Almost alerted (55–69)', color: 'var(--severity-medium)' },
  elevated: { label: 'Worth a review (40–54)', color: 'var(--severity-low)' },
  low: { label: 'Looks normal (0–39)', color: 'var(--muted-foreground)' },
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
  const pctLabel = alertedPct < 1 ? alertedPct.toFixed(1) : String(Math.round(alertedPct))
  return (
    <div className="space-y-4">
      {/* Plain-language framing for a non-technical reader */}
      <p className="text-xs leading-relaxed text-muted-foreground">
        Every privileged action is screened. A few are alarming enough to raise an{' '}
        <span className="text-foreground">alert</span>; most look normal. This is the small group
        sitting <span className="text-foreground">just below the alert line</span> — people worth
        keeping an eye on before anything escalates.
      </p>

      {/* From everything screened → down to what actually alerted */}
      <div className="space-y-2.5">
        <FunnelStage
          label="Actions screened this week"
          count={data.total_scored}
          total={data.total_scored}
          color="var(--primary)"
        />
        <FunnelStage
          label="Below the alert line — being watched"
          count={data.sub_threshold}
          total={data.total_scored}
          color="var(--severity-medium)"
          hint={`${Math.round((data.sub_threshold / Math.max(1, data.total_scored)) * 100)}%`}
        />
        <FunnelStage
          label="Raised as alerts"
          count={data.alerted}
          total={data.total_scored}
          color="var(--severity-high)"
          hint={`${pctLabel}%`}
        />
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-severity-medium/30 bg-severity-medium/10 px-3 py-2 text-xs text-severity-medium">
        <TrendingDown className="mt-0.5 size-4 shrink-0" />
        <p className="leading-relaxed text-foreground/85">
          Just <span className="font-mono tabular-nums">{pctLabel}%</span> of activity was alarming
          enough to alert. The <span className="font-medium">{nf.format(data.sub_threshold)}</span>{' '}
          below the line are near-misses and slow-drift staff — the watch list catches them early,
          before they’d ever trip an alert.
        </p>
      </div>

      {/* How the watched activity splits */}
      <div className="space-y-1.5">
        <Eyebrow>How the watched activity splits</Eyebrow>
        {data.bands.map((b) => {
          const meta = BAND_META[b.label] ?? {
            label: humanize(b.label),
            color: 'var(--muted-foreground)',
          }
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

      {/* People to keep an eye on — highest scorers still below the alert line */}
      {data.watchlist.length > 0 ? (
        <div className="space-y-1.5">
          <Eyebrow>People to keep an eye on · highest below the line</Eyebrow>
          <ul className="divide-y divide-border/60 rounded-lg border border-border/60">
            {data.watchlist.map((w) => (
              <li key={w.entity_id} className="flex items-center gap-3 px-3 py-1.5 text-xs">
                <span
                  className="w-8 shrink-0 text-center font-mono font-semibold tabular-nums"
                  style={{ color: riskColor(w.score) }}
                  title={`Risk score ${w.score} of 100 — below the 70 alert line`}
                >
                  {w.score}
                </span>
                <span className="w-24 shrink-0 truncate font-mono text-foreground">
                  {w.entity_id}
                </span>
                <span
                  className="flex-1 truncate text-muted-foreground"
                  title={featureFriendlyLabel(w.top_signal)}
                >
                  {featureFriendlyLabel(w.top_signal)}
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
          Watch list · activity just below the alert line
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
