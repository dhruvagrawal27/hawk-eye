/**
 * PeerStrip — peer-relative deviation marker (docs/ui/UI_UPLIFT.md §3).
 *
 * Hawk-Eye scoring is **peer-relative** (an action is suspicious relative to the actor's cohort, not
 * in absolute terms). This strip places a value on a horizontal scale with the peer **mean** and
 * **p95** marked, so an investigator sees "how far outside the cohort" at a glance. The marker colours
 * by how far past p95 the value sits (calm → ember). Pure SVG-free (divs), safe in dense tables.
 */
import { cn } from '@/lib/cn'
import { riskColor } from '@/lib/risk'

export interface PeerStripProps {
  /** The subject's value. */
  value: number
  /** Cohort mean. */
  peerMean: number
  /** Cohort 95th percentile — the "outlier" threshold. */
  peerP95: number
  /** Scale bounds; default to a sensible pad around the data. */
  min?: number
  max?: number
  label?: string
  className?: string
}

export function PeerStrip({
  value,
  peerMean,
  peerP95,
  min,
  max,
  label,
  className,
}: PeerStripProps) {
  const lo = min ?? Math.min(0, value, peerMean, peerP95)
  const hi = max ?? (Math.max(value, peerP95, peerMean) * 1.1 || 1)
  const span = hi - lo || 1
  const pct = (v: number) => `${Math.min(100, Math.max(0, ((v - lo) / span) * 100))}%`

  // Deviation past p95 drives the marker colour (0 at p95 → 100 well beyond).
  const over = peerP95 > peerMean ? (value - peerP95) / (peerP95 - peerMean) : 0
  const intensity = value <= peerMean ? 10 : value <= peerP95 ? 45 : Math.min(100, 70 + over * 20)
  const markerColor = riskColor(intensity)

  return (
    <div className={cn('w-full', className)}>
      {label ? (
        <div className="mb-1 flex items-baseline justify-between">
          <span className="text-2xs uppercase tracking-widest text-muted-foreground">{label}</span>
          <span className="font-mono text-2xs tabular-nums" style={{ color: markerColor }}>
            {value > peerP95 ? 'outlier' : value > peerMean ? 'above peer' : 'in cohort'}
          </span>
        </div>
      ) : null}
      <div
        className="relative h-2 w-full rounded-full bg-muted"
        role="img"
        aria-label={
          `${label ? label + ': ' : ''}value ${value}, peer mean ${peerMean}, p95 ${peerP95}` +
          `, ${value > peerP95 ? 'outlier' : value > peerMean ? 'above peer average' : 'within cohort'}`
        }
      >
        {/* Cohort band: mean → p95 */}
        <div
          className="absolute inset-y-0 rounded-full bg-foreground/10"
          style={{ left: pct(peerMean), right: `calc(100% - ${pct(peerP95)})` }}
        />
        {/* Mean tick */}
        <div
          className="absolute inset-y-[-2px] w-px bg-muted-foreground"
          style={{ left: pct(peerMean) }}
          aria-hidden
        />
        {/* p95 tick (dashed feel via a thin double) */}
        <div
          className="absolute inset-y-[-3px] w-px bg-foreground/50"
          style={{ left: pct(peerP95) }}
          aria-hidden
        />
        {/* Value marker */}
        <div
          className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background shadow-sm"
          style={{ left: pct(value), backgroundColor: markerColor }}
          aria-hidden
        />
      </div>
    </div>
  )
}
