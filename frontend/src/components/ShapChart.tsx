/**
 * SHAP contribution **waterfall** — the L3 (GBDT) feature attribution that makes a score
 * SAR/FMR-defensible. Each feature *steps* the running risk up or down from a baseline: positive
 * contributions push risk higher (ember, growing rightward), negative ones pull it back (calm green,
 * growing leftward). Sorted by |contribution| so the dominant drivers sit at the top; feature names are
 * monospaced (forensic evidence). Bars ease in from the baseline with a short stagger and collapse to
 * instant under `prefers-reduced-motion`. Pure divs + Motion — no chart dependency.
 * (Blueprint Part 11 / Part 24.4 §4.)
 */
import { BarChartHorizontal } from 'lucide-react'
import { humanize, formatSigned } from '@/lib/format'
import { EmptyState } from '@/components/ui/empty-state'
import { m, useReducedMotionSafe } from '@/ui'
import type { ShapContribution } from '@/lib/types'

const RISK_UP = 'hsl(var(--severity-high))' // pushes risk up
const RISK_DOWN = 'hsl(var(--reason-graph))' // calm green — pulls risk down

interface Row {
  feature: string
  label: string
  contribution: number
  value?: number | string
  increases: boolean
}

function buildRows(features: ShapContribution[]): Row[] {
  return features
    .map((f) => ({
      feature: f.feature,
      label: humanize(f.feature),
      contribution: f.contribution,
      value: f.value,
      increases: f.direction != null ? f.direction === 'increases_risk' : f.contribution >= 0,
    }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
}

export function ShapChart({ features }: { features: ShapContribution[] }) {
  const reduce = useReducedMotionSafe()
  const rows = buildRows(features)

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={BarChartHorizontal}
        title="No SHAP attribution"
        description="The fusion model returned no per-feature contributions for this alert."
      />
    )
  }

  // Cumulative waterfall: walk the running total feature-by-feature so each bar starts where the
  // previous one ended. Scale every bar to the full swing of the walk (incl. the 0 baseline).
  let cum = 0
  const steps = rows.map((r) => {
    const from = cum
    cum += r.contribution
    return { ...r, from, to: cum }
  })
  const total = cum
  const bounds = steps.flatMap((s) => [s.from, s.to])
  bounds.push(0)
  const lo = Math.min(...bounds)
  const hi = Math.max(...bounds)
  const span = hi - lo || 1
  const posPct = (v: number) => ((v - lo) / span) * 100
  const zeroPct = posPct(0)

  return (
    <div>
      <div
        className="space-y-1.5"
        role="img"
        aria-label={`SHAP contribution waterfall over ${rows.length} features; net contribution ${formatSigned(total)}`}
      >
        {steps.map((s, i) => {
          const left = Math.min(s.from, s.to)
          const leftPct = posPct(left)
          const widthPct = Math.max((Math.abs(s.contribution) / span) * 100, 1.5)
          const color = s.increases ? RISK_UP : RISK_DOWN
          return (
            <div
              key={s.feature}
              className="group flex items-center gap-2"
              title={`${s.label}: ${formatSigned(s.contribution)} (${
                s.increases ? 'increases' : 'decreases'
              } risk)${s.value != null ? ` · value ${s.value}` : ''}`}
            >
              <span className="w-40 shrink-0 truncate text-right font-mono text-xs text-foreground">
                {s.label}
              </span>
              <div className="relative h-5 flex-1 rounded bg-muted/40 ring-1 ring-inset ring-border/50 transition-colors group-hover:bg-muted/70">
                {/* zero baseline the walk pushes/pulls against */}
                <div
                  className="absolute inset-y-0 w-px bg-border"
                  style={{ left: `${zeroPct}%` }}
                  aria-hidden
                />
                <m.div
                  className="absolute inset-y-1 rounded-sm"
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                    backgroundColor: color,
                    transformOrigin: s.increases ? 'left' : 'right',
                  }}
                  initial={reduce ? false : { scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={
                    reduce
                      ? { duration: 0 }
                      : { duration: 0.5, delay: Math.min(i * 0.05, 0.6), ease: [0.16, 1, 0.3, 1] }
                  }
                />
              </div>
              <span
                className="w-14 shrink-0 text-right font-mono text-xs tabular-nums"
                style={{ color }}
              >
                {formatSigned(s.contribution)}
              </span>
            </div>
          )
        })}
      </div>

      {/* Net contribution — where the walk lands. */}
      <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-xs">
        <span className="text-muted-foreground">Net feature contribution to risk</span>
        <span
          className="font-mono font-semibold tabular-nums"
          style={{ color: total >= 0 ? RISK_UP : RISK_DOWN }}
        >
          {formatSigned(total)}
        </span>
      </div>

      <div className="mt-1 flex items-center justify-center gap-4 text-2xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-sm" style={{ background: RISK_UP }} aria-hidden />
          increases risk
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-sm" style={{ background: RISK_DOWN }} aria-hidden />
          decreases risk
        </span>
      </div>
    </div>
  )
}
