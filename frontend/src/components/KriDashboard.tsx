/**
 * Management + board (SCBMF) KRI dashboard (FRONTEND-13; blueprint Part 11 reporting + Part 24.4).
 *
 * Three surfaces against a single `KriResponse`:
 *   1. KRI cards — value vs target, RAG status, and period-over-period delta arrow (alert volume vs
 *      capacity, MTTD, FPR, SLA/TAT compliance, open high/critical, coverage).
 *   2. Trends — a stacked area + line chart of the weekly series (alerts / confirmed / FPs / MTTD).
 *   3. Coverage map — a horizontal bar per area (typology / unit / branch) coloured by coverage %.
 *
 * All aggregate, board-level figures — no case PII. Charts live in fixed-height containers.
 */
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatNumber } from '@/lib/format'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/empty-state'
import { AmountFlip, CountUp, Sparkline, m, staggerParent, staggerItem } from '@/ui'
import type { KriCard, KriResponse, KriTrendPoint } from '@/lib/types'

const STATUS_RING: Record<NonNullable<KriCard['status']>, string> = {
  ok: 'ring-sla-ok/40',
  warning: 'ring-sla-warn/40',
  breach: 'ring-severity-critical/40',
}
const STATUS_DOT: Record<NonNullable<KriCard['status']>, string> = {
  ok: 'bg-sla-ok',
  warning: 'bg-sla-warn',
  breach: 'bg-severity-critical',
}
const STATUS_LABEL: Record<NonNullable<KriCard['status']>, string> = {
  ok: 'On target',
  warning: 'Watch',
  breach: 'Breach',
}
/** CSS var name driving the per-card sparkline stroke — matches the RAG status dot. */
const STATUS_STROKE: Record<NonNullable<KriCard['status']>, string> = {
  ok: 'sla-ok',
  warning: 'sla-warn',
  breach: 'severity-critical',
}

/** Suffix the unit onto a formatted numeral, matching the static form ("42%", "3.1 d", "128"). */
function withUnit(text: string, unit?: string): string {
  if (!unit) return text
  return unit === '%' ? `${text}%` : `${text} ${unit}`
}

/**
 * Format a card value the way the static dashboard did — integers grouped, decimals to 1dp — so the
 * animated roll-up lands on exactly the figure a board pack would print. Used as the CountUp/AmountFlip
 * `aria-label` value + in-flight formatter, so screen readers only ever hear the final number.
 */
function formatKriValue(value: number, unit?: string): string {
  const num = Number.isInteger(value) ? formatNumber(value) : value.toFixed(1)
  return withUnit(num, unit)
}

/**
 * The animated headline figure for a KRI card. Plain counts (no unit / a `%`) roll up with the generic
 * CountUp; anything the board reads as money (₹/INR unit) uses the INR-grouped AmountFlip. Both degrade
 * to the final value instantly under reduced motion.
 */
function KriValue({ card }: { card: KriCard }) {
  const unit = card.unit ?? ''
  const isMoney = unit === '₹' || /inr/i.test(unit)
  const className = 'mt-1 block font-mono text-2xl font-semibold tabular-nums text-foreground'

  if (isMoney) {
    return <AmountFlip value={card.value} kind="inr" compact className={className} />
  }
  return (
    <CountUp
      value={card.value}
      decimals={Number.isInteger(card.value) ? 0 : 1}
      className={className}
      format={(n) => formatKriValue(n, unit)}
    />
  )
}

/** A delta is "good" when it moves in the card's preferred direction. */
function deltaTone(card: KriCard): 'good' | 'bad' | 'flat' {
  if (card.delta == null || card.delta === 0) return 'flat'
  const lowerBetter = card.direction === 'lower_is_better'
  const improving = lowerBetter ? card.delta < 0 : card.delta > 0
  return improving ? 'good' : 'bad'
}

function KriCardView({ card, trend }: { card: KriCard; trend?: number[] }) {
  const status = card.status ?? 'ok'
  const tone = deltaTone(card)
  const DeltaIcon =
    card.delta == null || card.delta === 0 ? Minus : card.delta > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <Card className={cn('ring-1 ring-inset', STATUS_RING[status])}>
      <CardContent className="p-3.5">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs text-muted-foreground">{card.label}</p>
          <span
            className="inline-flex items-center gap-1 text-[0.7rem] font-medium text-muted-foreground"
            title={STATUS_LABEL[status]}
          >
            <span className={cn('size-2 rounded-full', STATUS_DOT[status])} aria-hidden />
            {STATUS_LABEL[status]}
          </span>
        </div>
        <div className="mt-1 flex items-end justify-between gap-2">
          <KriValue card={card} />
          {trend && trend.length >= 2 ? (
            <Sparkline
              points={trend}
              width={64}
              height={22}
              stroke={`hsl(var(--${STATUS_STROKE[status]}))`}
              area
              className="mb-1 shrink-0"
              aria-label={`${card.label} trend`}
            />
          ) : null}
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[0.7rem]">
          <span className="text-muted-foreground">
            {card.target != null ? (
              <>
                target{' '}
                <span className="font-mono tabular-nums text-foreground">
                  {card.unit === '%' ? `${card.target}%` : formatNumber(card.target)}
                </span>
              </>
            ) : (
              'no target'
            )}
          </span>
          {card.delta != null ? (
            <span
              className={cn(
                'inline-flex items-center gap-0.5 font-mono tabular-nums',
                tone === 'good' && 'text-sla-ok',
                tone === 'bad' && 'text-severity-high',
                tone === 'flat' && 'text-muted-foreground',
              )}
              title="vs previous period"
            >
              <DeltaIcon className="size-3" />
              {card.delta > 0 ? '+' : ''}
              {card.delta}
              {card.unit === '%' ? '%' : ''}
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

/**
 * Extract a card's own history from the weekly trend rows for its inline sparkline: the numeric series
 * whose key matches the card `key` (chronological, oldest→newest). Returns `undefined` when the KRI has
 * no matching series so the card simply omits its sparkline (honest — never a fabricated line).
 */
function trendForCard(card: KriCard, trends: KriTrendPoint[]): number[] | undefined {
  const series: number[] = []
  for (const row of trends) {
    const v = row[card.key]
    if (typeof v === 'number') series.push(v)
  }
  return series.length >= 2 ? series : undefined
}

/** Pick numeric series keys present on the trend rows (excludes the `period` label). */
function trendSeriesKeys(trends: KriTrendPoint[]): string[] {
  const keys = new Set<string>()
  for (const row of trends) {
    for (const [k, v] of Object.entries(row)) {
      if (k !== 'period' && typeof v === 'number') keys.add(k)
    }
  }
  return [...keys]
}

const SERIES_COLOR: Record<string, string> = {
  alerts: 'hsl(var(--primary))',
  confirmed: 'hsl(var(--severity-critical))',
  false_positives: 'hsl(var(--muted-foreground))',
  mttd: 'hsl(var(--reason-graph))',
}
function seriesColor(key: string, index: number): string {
  return SERIES_COLOR[key] ?? `hsl(var(--chart-${(index % 4) + 1}, var(--primary)))`
}
function humanizeKey(key: string): string {
  return key
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bMttd\b/, 'MTTD')
    .replace(/\bFpr\b/, 'FPR')
}

function coverageColor(pct: number): string {
  if (pct >= 90) return 'hsl(var(--sla-ok))'
  if (pct >= 80) return 'hsl(var(--sla-warn))'
  return 'hsl(var(--severity-high))'
}

export function KriDashboard({ data }: { data: KriResponse }) {
  const trendKeys = trendSeriesKeys(data.trends)
  const areaKeys = trendKeys.filter((k) => k !== 'mttd')
  const hasMttd = trendKeys.includes('mttd')

  return (
    <div className="space-y-4">
      {/* KRI cards — a tasteful reveal-on-load stagger cascades the board figures in (reduced-motion
          shows them all at once; the numbers themselves roll up via CountUp/AmountFlip). */}
      {data.cards.length === 0 ? (
        <EmptyState
          title="No KRIs published"
          description="The reporting service returned no KRI cards for this period."
        />
      ) : (
        <m.div
          className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6"
          variants={staggerParent}
          initial="hidden"
          animate="show"
        >
          {data.cards.map((card) => (
            <m.div key={card.key} variants={staggerItem}>
              <KriCardView card={card} trend={trendForCard(card, data.trends)} />
            </m.div>
          ))}
        </m.div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Trends */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="font-display">Detection trends</CardTitle>
            <CardDescription>
              Weekly alert volume, confirmed fraud, false positives, and mean-time-to-detect.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {data.trends.length === 0 ? (
              <EmptyState title="No trend data" />
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data.trends} margin={{ top: 6, right: 8, bottom: 0, left: -20 }}>
                    <defs>
                      {areaKeys.map((key, i) => (
                        <linearGradient key={key} id={`kri-${key}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={seriesColor(key, i)} stopOpacity={0.35} />
                          <stop offset="95%" stopColor={seriesColor(key, i)} stopOpacity={0.03} />
                        </linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border))"
                      opacity={0.4}
                    />
                    <XAxis
                      dataKey="period"
                      tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                      tickLine={false}
                      axisLine={{ stroke: 'hsl(var(--border))' }}
                      minTickGap={20}
                    />
                    <YAxis
                      yAxisId="count"
                      tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                      tickLine={false}
                      axisLine={false}
                      width={36}
                    />
                    {hasMttd ? (
                      <YAxis
                        yAxisId="mttd"
                        orientation="right"
                        tick={{ fontSize: 10, fill: 'hsl(var(--reason-graph))' }}
                        tickLine={false}
                        axisLine={false}
                        width={30}
                      />
                    ) : null}
                    <RTooltip
                      contentStyle={{
                        background: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 11 }}
                      formatter={(v) => humanizeKey(String(v))}
                    />
                    {areaKeys.map((key, i) => (
                      <Area
                        key={key}
                        yAxisId="count"
                        type="monotone"
                        dataKey={key}
                        stroke={seriesColor(key, i)}
                        strokeWidth={2}
                        fill={`url(#kri-${key})`}
                        isAnimationActive={false}
                      />
                    ))}
                    {hasMttd ? (
                      <Line
                        yAxisId="mttd"
                        type="monotone"
                        dataKey="mttd"
                        stroke={SERIES_COLOR.mttd}
                        strokeWidth={2}
                        strokeDasharray="5 3"
                        dot={false}
                        isAnimationActive={false}
                      />
                    ) : null}
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Coverage map */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="font-display">Coverage by area</CardTitle>
            <CardDescription>Typology / unit coverage of the detection estate.</CardDescription>
          </CardHeader>
          <CardContent>
            {data.coverage.length === 0 ? (
              <EmptyState title="No coverage data" />
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    layout="vertical"
                    data={data.coverage}
                    margin={{ top: 4, right: 36, bottom: 0, left: 8 }}
                    barCategoryGap={8}
                  >
                    <CartesianGrid
                      horizontal={false}
                      strokeDasharray="3 3"
                      stroke="hsl(var(--border))"
                      opacity={0.4}
                    />
                    <XAxis
                      type="number"
                      domain={[0, 100]}
                      tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                      tickLine={false}
                      axisLine={{ stroke: 'hsl(var(--border))' }}
                      tickFormatter={(v: number) => `${v}%`}
                    />
                    <YAxis
                      type="category"
                      dataKey="area"
                      width={104}
                      tick={{ fontSize: 11, fill: 'hsl(var(--foreground))' }}
                      tickLine={false}
                      axisLine={false}
                      interval={0}
                    />
                    <RTooltip
                      cursor={{ fill: 'hsl(var(--muted))', opacity: 0.4 }}
                      contentStyle={{
                        background: 'hsl(var(--popover))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      formatter={(v) => [`${v}%`, 'covered']}
                    />
                    <Bar dataKey="covered_pct" radius={[3, 3, 3, 3]} isAnimationActive={false}>
                      {data.coverage.map((c) => (
                        <Cell key={c.area} fill={coverageColor(c.covered_pct)} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
