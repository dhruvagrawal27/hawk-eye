/**
 * Live events/sec area chart (study Phase 1 · status strip).
 *
 * Reads the rolling 60-bucket window from `useEventRate` — the ONE 1s ring buffer that powers both
 * this sparkline and the status-bar EPS — and renders it as a stepped area: ticker-cyan for events,
 * a faint risk-high overlay for the (rarer) alerts. Deliberately compact and chrome-light so it can
 * embed in the dashboard/status area: no axis labels, no grid, just the shape + a live-EPS header.
 *
 * Recharts is held flat per the prototype rules — isAnimationActive={false}, type='step', bounded
 * window — so the chart never animates/tweens on each 1s roll (which would look like noise, not data).
 */
import { Area, AreaChart, ResponsiveContainer, YAxis } from 'recharts'
import { Eyebrow } from '@/components/ui/eyebrow'
import { useEventRate } from '@/hooks/useRealtime'
import { cn } from '@/lib/cn'

const EVENTS_COLOR = 'hsl(var(--ticker))'
const ALERTS_COLOR = 'hsl(var(--severity-high))'

export interface EventRateChartProps {
  /** Plot height in px (header sits above it). Default 64 — sparkline-compact. */
  height?: number
}

export function EventRateChart({ height = 64 }: EventRateChartProps) {
  const { buckets, eps, live } = useEventRate(60)

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <Eyebrow className="flex items-center gap-1.5">
          <span
            className={cn(
              'inline-block size-1.5 rounded-full',
              live ? 'bg-ticker motion-safe:animate-pulse-soft' : 'bg-muted-foreground/40',
            )}
            aria-hidden
          />
          Events / sec
        </Eyebrow>
        <span className="font-mono text-sm font-semibold tabular-nums text-ticker">
          {eps.toFixed(1)}
        </span>
      </div>

      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={buckets} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="evrate-events-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={EVENTS_COLOR} stopOpacity={0.35} />
                <stop offset="100%" stopColor={EVENTS_COLOR} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            {/* Hidden, auto-scaled axis keeps both series sharing one bounded domain without label clutter. */}
            <YAxis hide domain={[0, 'auto']} />
            <Area
              type="step"
              dataKey="events"
              stroke={EVENTS_COLOR}
              strokeWidth={1.5}
              fill="url(#evrate-events-fill)"
              isAnimationActive={false}
              dot={false}
              activeDot={false}
              connectNulls
            />
            <Area
              type="step"
              dataKey="alerts"
              stroke={ALERTS_COLOR}
              strokeWidth={1}
              strokeOpacity={0.8}
              fill={ALERTS_COLOR}
              fillOpacity={0.12}
              isAnimationActive={false}
              dot={false}
              activeDot={false}
              connectNulls
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
