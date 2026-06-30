/**
 * Six-layer detection waterfall (the "how this score was built" headline). Shows each detection layer
 * L1→L5 as a contribution bar building up to the fused L6 risk, against the decision threshold, with a
 * "rescued by graph" / "confirmed by sequence" insight. This is what distinguishes our 6-layer stack
 * from a 3-stream blend. Data: lib/layerFusion.deriveLayerBreakdown(alert, fusion?).
 */
import { ShieldCheck, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/cn'
import { deriveLayerBreakdown } from '@/lib/layerFusion'
import type { Alert, FusionBreakdown } from '@/lib/types'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'

export function LayerWaterfall({
  alert,
  fusion,
  className,
}: {
  alert: Alert
  fusion?: FusionBreakdown | null
  className?: string
}) {
  const b = deriveLayerBreakdown(alert, fusion)
  const scale = Math.max(b.fused, b.threshold, 1)

  // running cumulative so each fired layer's bar starts where the previous ended (a true waterfall)
  let cum = 0

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <div className="flex items-baseline justify-between">
        <Eyebrow>Detection layers · how this score was built</Eyebrow>
        <span className="font-mono text-2xs text-muted-foreground">
          threshold {b.threshold}
        </span>
      </div>

      {/* fused headline */}
      <div className="flex items-end gap-2">
        <span
          className="font-mono text-3xl font-semibold leading-none tabular-nums"
          style={{ color: 'hsl(var(--severity-high))' }}
        >
          {b.fused}
        </span>
        <span className="pb-0.5 text-2xs uppercase tracking-widest text-muted-foreground">
          fused L6 risk
        </span>
      </div>

      {/* stacked cumulative bar with threshold tick */}
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-muted/50">
        {b.layers
          .filter((l) => l.fired)
          .map((l) => {
            const left = (cum / scale) * 100
            const w = (l.contribution / scale) * 100
            cum += l.contribution
            return (
              <span
                key={l.layer}
                className="absolute inset-y-0"
                style={{ left: `${left}%`, width: `${w}%`, backgroundColor: `hsl(${l.accentVar})` }}
                title={`${l.label}: +${l.contribution}`}
              />
            )
          })}
        {/* threshold marker */}
        <span
          aria-hidden
          className="absolute inset-y-[-2px] w-0.5 bg-foreground/70"
          style={{ left: `${(b.threshold / scale) * 100}%` }}
        />
      </div>

      {/* per-layer rows */}
      <div className="space-y-1.5">
        {b.layers.map((l) => (
          <div
            key={l.layer}
            className={cn('flex items-center gap-3', !l.fired && 'opacity-40')}
          >
            <div className="w-40 shrink-0">
              <p className="truncate text-xs font-medium">{l.label}</p>
              <p className="font-mono text-3xs uppercase tracking-wider text-muted-foreground">
                {l.sub}
              </p>
            </div>
            <div className="relative h-3 flex-1 overflow-hidden rounded bg-muted/40">
              <span
                className="absolute inset-y-0 left-0 rounded"
                style={{
                  width: `${(l.contribution / scale) * 100}%`,
                  backgroundColor: `hsl(${l.accentVar})`,
                }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums">
              {l.fired ? `+${l.contribution}` : '—'}
            </span>
          </div>
        ))}

        {/* fused total row */}
        <div className="flex items-center gap-3 border-t border-border/60 pt-1.5">
          <div className="w-40 shrink-0">
            <p className="truncate text-xs font-semibold">Fused risk</p>
            <p className="font-mono text-3xs uppercase tracking-wider text-muted-foreground">
              L6 · meta-learner
            </p>
          </div>
          <div className="flex-1" />
          <span
            className="w-12 shrink-0 text-right font-mono text-sm font-semibold tabular-nums"
            style={{ color: 'hsl(var(--severity-high))' }}
          >
            {b.fused}
          </span>
        </div>
      </div>

      {/* rescue / confirmation insight */}
      {b.rescued && b.decisive ? (
        <div className="flex items-start gap-2 rounded-lg border border-reason-graph/30 bg-reason-graph/10 px-3 py-2 text-xs text-reason-graph">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" />
          <p className="leading-relaxed text-foreground/85">
            <span className="font-semibold text-reason-graph">Rescued by {b.decisive.label}.</span>{' '}
            Gradient-boosted trees alone scored {b.layers.find((l) => l.layer === 'L3_gbdt')?.contribution ?? 0} —
            below the {b.threshold} threshold. {b.decisive.label} (L{b.decisive.layer.match(/\d/)?.[0]})
            carried it to {b.fused}. A tabular-only model would have missed this.
          </p>
        </div>
      ) : b.decisive ? (
        <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          <TrendingUp className="mt-0.5 size-4 shrink-0" />
          <p className="leading-relaxed text-foreground/80">
            Multiple layers concur — strongest lift from{' '}
            <span className="font-medium text-foreground">{b.decisive.label}</span>.
          </p>
        </div>
      ) : null}
    </Surface>
  )
}
