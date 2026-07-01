/**
 * SHAP contribution chart — the L3 (GBDT) feature attribution that makes a score SAR/FMR-defensible:
 * every feature is shown with its *signed* push on the fused risk score. Positive contributions
 * increase risk (severity colour); negative contributions decrease it (muted/green). Sorted by
 * |contribution| so the dominant drivers sit at the top. (Blueprint Part 11 / Part 24.4 §4.)
 */
import {
  Bar,
  BarChart,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import { BarChartHorizontal } from 'lucide-react'
import { humanize, formatSigned } from '@/lib/format'
import { EmptyState } from '@/components/ui/empty-state'
import type { ShapContribution } from '@/lib/types'

const RISK_UP = 'hsl(var(--severity-high))'
const RISK_DOWN = 'hsl(var(--reason-graph))' // calm green — pushes risk down

interface Row {
  feature: string
  label: string
  contribution: number
  value?: number | string
  percentile?: number
  increases: boolean
}

function buildRows(features: ShapContribution[]): Row[] {
  return features
    .map((f) => ({
      feature: f.feature,
      label: humanize(f.feature),
      contribution: f.contribution,
      value: f.value,
      percentile: f.percentile,
      increases: f.direction != null ? f.direction === 'increases_risk' : f.contribution >= 0,
    }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
}

function ShapTooltip({ active, payload }: Partial<TooltipContentProps<number, string>>) {
  if (!active || !payload || payload.length === 0) return null
  const row = payload[0].payload as Row
  return (
    <div className="rounded-md border border-border bg-popover px-2.5 py-1.5 text-xs shadow-md">
      <div className="font-medium text-popover-foreground">{row.label}</div>
      <div className="mt-0.5 flex items-center gap-2 tabular-nums">
        <span style={{ color: row.increases ? RISK_UP : RISK_DOWN }}>
          {formatSigned(row.contribution)}
        </span>
        <span className="text-muted-foreground">
          {row.increases ? 'increases risk' : 'decreases risk'}
        </span>
      </div>
      {row.value != null ? (
        <div className="mt-0.5 text-muted-foreground">
          value: <span className="tabular-nums text-foreground">{String(row.value)}</span>
        </div>
      ) : null}
      {row.percentile != null ? (
        <div className="text-muted-foreground">
          peer percentile:{' '}
          <span className="tabular-nums text-foreground">p{Math.round(row.percentile * 100)}</span>{' '}
          <span className="text-[0.65rem]">(vs comparable peers)</span>
        </div>
      ) : null}
    </div>
  )
}

export function ShapChart({
  features,
  synthesized = false,
}: {
  features: ShapContribution[]
  synthesized?: boolean
}) {
  const rows = buildRows(features)

  if (rows.length === 0) {
    return (
      <EmptyState
        icon={BarChartHorizontal}
        title="No feature attribution for this alert"
        description="This alert fired on deterministic rules or graph evidence only — the supervised model (L3) did not score it, so there are no per-feature contributions to show."
      />
    )
  }

  const max = Math.max(...rows.map((r) => Math.abs(r.contribution)), 0.01)
  // ~30px per row keeps dense rows legible; floor so small sets still look intentional.
  const height = Math.max(180, rows.length * 30 + 24)

  return (
    <div>
      <p className="mb-1.5 text-2xs leading-relaxed text-muted-foreground">
        Each bar is a feature’s <span className="text-foreground">signed push</span> on the risk
        score: bars to the right (red) increased risk, bars to the left (green) reduced it; longer =
        stronger.
        {synthesized ? (
          <span className="ml-1 rounded bg-muted px-1 py-0.5 text-[0.65rem] text-amber-500/90">
            illustrative — derived from this alert’s fired signals, not a fitted-GBDT SHAP run
          </span>
        ) : null}
      </p>
      <div style={{ height }} className="w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={rows}
            margin={{ top: 4, right: 48, bottom: 4, left: 8 }}
            barCategoryGap={6}
          >
            <XAxis
              type="number"
              domain={[-max * 1.1, max * 1.1]}
              tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
              tickFormatter={(v: number) => formatSigned(v, 2)}
              axisLine={{ stroke: 'hsl(var(--border))' }}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={150}
              tick={{ fontSize: 11, fill: 'hsl(var(--foreground))' }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <RTooltip
              cursor={{ fill: 'hsl(var(--muted))', opacity: 0.4 }}
              content={<ShapTooltip />}
            />
            <ReferenceLine x={0} stroke="hsl(var(--border))" strokeWidth={1.5} />
            <Bar dataKey="contribution" radius={[3, 3, 3, 3]} isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.feature} fill={r.increases ? RISK_UP : RISK_DOWN} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex items-center justify-center gap-4 text-[0.7rem] text-muted-foreground">
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
