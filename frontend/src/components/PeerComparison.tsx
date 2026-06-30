import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ScatterChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Scatter,
  ReferenceArea,
  ReferenceLine,
  Tooltip as RechartsTooltip,
} from 'recharts'
import { Users, TriangleAlert, ArrowUpRight, ArrowDownRight, ScaleIcon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { clamp, formatNumber, formatSigned, humanize } from '@/lib/format'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { EmptyState } from '@/components/ui/empty-state'
import { Skeleton } from '@/components/ui/skeleton'
import { InfoTip } from '@/components/ui/tooltip'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { PeerDimension, PeerDistribution } from '@/lib/types'

/* ── Chart palette (resolved at render so dark mode flips correctly) ─────────── */
const C = {
  box: 'hsl(var(--muted-foreground))',
  whisker: 'hsl(var(--border))',
  median: 'hsl(var(--primary))',
  sample: 'hsl(var(--muted-foreground))',
  actor: 'hsl(var(--severity-critical))',
  actorOk: 'hsl(var(--severity-low))',
  grid: 'hsl(var(--border))',
} as const

/* ── Derived peer-anchored stats — makes "abnormal" concrete and fair ────────── */
interface DimStats {
  /** Empirical percentile of the actor inside the peer sample (0–1), if samples exist. */
  percentile: number | null
  /** |z| derived from distribution if z_score absent. */
  zScore: number | null
  /** True when the actor sits past the *risky* tail (direction-aware). */
  beyondRiskyTail: boolean
  /** True when actor falls outside the [p25, p75] inter-quartile box. */
  outsideIqr: boolean
}

function deriveStats(dim: PeerDimension): DimStats {
  const d = dim.peer_distribution
  const samples = d.samples ?? []
  const percentile =
    samples.length > 0
      ? clamp(samples.filter((s) => s <= dim.actor_value).length / samples.length, 0, 1)
      : null

  let zScore = dim.z_score ?? null
  if (zScore == null && d.stddev && d.stddev > 0) {
    zScore = (dim.actor_value - d.mean) / d.stddev
  }

  const higherRiskier = dim.direction !== 'lower_is_riskier'
  const beyondRiskyTail = higherRiskier ? dim.actor_value > d.p75 : dim.actor_value < d.p25
  const outsideIqr = dim.actor_value < d.p25 || dim.actor_value > d.p75

  return { percentile, zScore, beyondRiskyTail, outsideIqr }
}

/** Deterministic jitter so the scatter doesn't reflow between renders. */
function pseudoJitter(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453
  return (x - Math.floor(x)) * 2 - 1 // -1..1
}

interface SamplePoint {
  value: number
  jitter: number
}

function formatValue(v: number, unit?: string): string {
  const n = formatNumber(v, Math.abs(v) < 10 ? 2 : 0)
  if (!unit) return n
  if (unit === '%') return `${n}%`
  if (unit === 'x' || unit === '×') return `${n}×`
  return `${n} ${unit}`
}

/* ── Box-whisker + jittered sample + actor marker for one dimension ──────────── */
const BAND_Y = 0.5

function DimensionChart({ dim }: { dim: PeerDimension }) {
  const d = dim.peer_distribution
  const stats = deriveStats(dim)
  const actorColor = stats.beyondRiskyTail ? C.actor : C.actorOk

  // Peer sample cloud — jittered around the band centre so density is visible.
  const samplePoints: SamplePoint[] = useMemo(
    () =>
      (d.samples ?? []).map((value, i) => ({ value, jitter: BAND_Y + pseudoJitter(i + 1) * 0.3 })),
    [d.samples],
  )
  // A single anchor point lets the actor's value get a tooltip on hover.
  const actorPoint: SamplePoint[] = useMemo(
    () => [{ value: dim.actor_value, jitter: BAND_Y }],
    [dim.actor_value],
  )

  const domain = useMemo<[number, number]>(() => {
    const lo = Math.min(d.min, dim.actor_value)
    const hi = Math.max(d.max, dim.actor_value)
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.08
    return [lo - pad, hi + pad]
  }, [d.min, d.max, dim.actor_value])

  return (
    <div className="h-44 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 18, right: 24, bottom: 8, left: 8 }}>
          <CartesianGrid horizontal={false} stroke={C.grid} strokeDasharray="3 3" opacity={0.5} />
          <XAxis
            type="number"
            dataKey="value"
            name="value"
            domain={domain}
            tick={{ fontSize: 11, fill: C.box }}
            tickFormatter={(v: number) => formatValue(v, dim.unit)}
            stroke={C.grid}
          />
          <YAxis
            type="number"
            dataKey="jitter"
            domain={[0, 1]}
            hide
            tick={false}
            axisLine={false}
          />
          <ZAxis range={[28, 28]} />
          <RechartsTooltip
            cursor={{ stroke: C.grid, strokeDasharray: '3 3' }}
            content={<DistTooltip dim={dim} stats={stats} />}
          />

          {/* Peer inter-quartile box (p25 → p75). */}
          <ReferenceArea
            x1={d.p25}
            x2={d.p75}
            y1={BAND_Y - 0.34}
            y2={BAND_Y + 0.34}
            fill={C.box}
            fillOpacity={0.14}
            stroke={C.box}
            strokeOpacity={0.5}
            ifOverflow="extendDomain"
          />
          {/* Min/max whiskers + connecting range line. */}
          <ReferenceLine
            segment={[
              { x: d.min, y: BAND_Y },
              { x: d.max, y: BAND_Y },
            ]}
            stroke={C.whisker}
            strokeWidth={1.5}
            ifOverflow="extendDomain"
          />
          <ReferenceLine x={d.min} stroke={C.whisker} strokeWidth={1.5} ifOverflow="extendDomain" />
          <ReferenceLine x={d.max} stroke={C.whisker} strokeWidth={1.5} ifOverflow="extendDomain" />
          {/* Median marker. */}
          <ReferenceLine x={d.median} stroke={C.median} strokeWidth={2} ifOverflow="extendDomain" />

          {/* Jittered peer sample cloud. */}
          {samplePoints.length > 0 ? (
            <Scatter
              data={samplePoints}
              fill={C.sample}
              fillOpacity={0.4}
              isAnimationActive={false}
            />
          ) : null}

          {/* Actor anchor (for hover) — the value itself is marked by the line below. */}
          <Scatter data={actorPoint} fill={actorColor} isAnimationActive={false} />

          {/* Actor's value — distinct, labelled line with the value/z-score. */}
          <ReferenceLine
            x={dim.actor_value}
            stroke={actorColor}
            strokeWidth={2.5}
            ifOverflow="extendDomain"
            label={{
              value: `Actor ${formatValue(dim.actor_value, dim.unit)}`,
              position: 'top',
              fontSize: 11,
              fill: actorColor,
              fontWeight: 600,
            }}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ── Tooltip describing the peer distribution + the actor delta ─────────────── */
function DistTooltip({ dim, stats }: { dim: PeerDimension; stats: DimStats }) {
  const d = dim.peer_distribution
  const rows: [string, number][] = [
    ['Min', d.min],
    ['p25', d.p25],
    ['Median', d.median],
    ['p75', d.p75],
    ['Max', d.max],
    ['Mean', d.mean],
  ]
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <div className="mb-1 font-semibold">{dim.label} — peer group</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 tabular-nums">
        {rows.map(([k, v]) => (
          <div key={k} className="flex justify-between gap-3">
            <span className="text-muted-foreground">{k}</span>
            <span>{formatValue(v, dim.unit)}</span>
          </div>
        ))}
      </div>
      <Separator className="my-1.5" />
      <div className="flex justify-between gap-3 tabular-nums">
        <span className="text-muted-foreground">Actor</span>
        <span className="font-semibold">{formatValue(dim.actor_value, dim.unit)}</span>
      </div>
      {stats.zScore != null ? (
        <div className="flex justify-between gap-3 tabular-nums">
          <span className="text-muted-foreground">z-score</span>
          <span>{formatSigned(stats.zScore)}σ</span>
        </div>
      ) : null}
      {stats.percentile != null ? (
        <div className="flex justify-between gap-3 tabular-nums">
          <span className="text-muted-foreground">Percentile</span>
          <span>{Math.round(stats.percentile * 100)}ᵗʰ</span>
        </div>
      ) : null}
    </div>
  )
}

/* ── A small read of how the actor compares, in plain language ──────────────── */
function ComparisonVerdict({ dim }: { dim: PeerDimension }) {
  const stats = deriveStats(dim)
  const higherRiskier = dim.direction !== 'lower_is_riskier'
  const above = dim.actor_value >= dim.peer_distribution.median
  const Arrow = above ? ArrowUpRight : ArrowDownRight

  let tone: 'risky' | 'watch' | 'normal' = 'normal'
  if (stats.beyondRiskyTail || (stats.zScore != null && Math.abs(stats.zScore) >= 2)) tone = 'risky'
  else if (stats.outsideIqr || (stats.zScore != null && Math.abs(stats.zScore) >= 1)) tone = 'watch'

  const toneClass =
    tone === 'risky'
      ? 'text-severity-high'
      : tone === 'watch'
        ? 'text-severity-medium'
        : 'text-severity-low'

  const percentileText =
    stats.percentile != null
      ? `${Math.round(stats.percentile * 100)}ᵗʰ percentile of ${dim.peer_distribution.samples?.length ?? ''} peers`
      : 'no peer sample for percentile'

  const verdict =
    tone === 'normal'
      ? 'In line with peers'
      : `${above ? 'Above' : 'Below'} the peer median — ${higherRiskier === above ? 'in the riskier direction' : 'in the safer direction'}`

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
      <span className={cn('inline-flex items-center gap-1 font-medium', toneClass)}>
        <Arrow className="size-3.5" />
        {verdict}
      </span>
      <span className="text-muted-foreground">·</span>
      <span className="tabular-nums text-muted-foreground">{percentileText}</span>
      {stats.zScore != null ? (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="tabular-nums text-muted-foreground">
            {formatSigned(stats.zScore)}σ from peer mean
          </span>
        </>
      ) : null}
    </div>
  )
}

/* ── Direction / unit / flagged chips for a dimension ───────────────────────── */
function DimensionMeta({ dim }: { dim: PeerDimension }) {
  const higherRiskier = dim.direction !== 'lower_is_riskier'
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {dim.flagged ? (
        <Badge variant="warning" className="gap-1">
          <TriangleAlert className="size-3" /> Flagged
        </Badge>
      ) : (
        <Badge variant="muted">Within range</Badge>
      )}
      <InfoTip
        label={
          higherRiskier
            ? 'Higher values are more risky for this dimension.'
            : 'Lower values are more risky for this dimension.'
        }
      >
        <Badge variant="outline" className="cursor-default gap-1">
          {higherRiskier ? (
            <ArrowUpRight className="size-3" />
          ) : (
            <ArrowDownRight className="size-3" />
          )}
          {higherRiskier ? 'Higher = riskier' : 'Lower = riskier'}
        </Badge>
      </InfoTip>
      {dim.unit ? (
        <Badge variant="muted" className="font-mono lowercase">
          {dim.unit}
        </Badge>
      ) : null}
    </div>
  )
}

/* ── Compact per-dimension list row (the "other" dimensions) ────────────────── */
function DimensionRow({
  dim,
  active,
  onSelect,
}: {
  dim: PeerDimension
  active: boolean
  onSelect: () => void
}) {
  const stats = deriveStats(dim)
  const d = dim.peer_distribution
  // Position of actor + median on a 0–100 track for a sparkline-style sense of place.
  const lo = Math.min(d.min, dim.actor_value)
  const hi = Math.max(d.max, dim.actor_value)
  const span = hi - lo || 1
  const pos = (v: number) => `${clamp(((v - lo) / span) * 100, 0, 100)}%`
  const boxLeft = clamp(((d.p25 - lo) / span) * 100, 0, 100)
  const boxRight = clamp(((d.p75 - lo) / span) * 100, 0, 100)

  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        'group flex w-full flex-col gap-1.5 rounded-md border px-3 py-2 text-left transition-colors focus-ring',
        active
          ? 'border-primary/40 bg-accent/50'
          : 'border-border hover:border-border hover:bg-accent/30',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium">{dim.label}</span>
        <span className="flex shrink-0 items-center gap-1.5">
          {dim.flagged ? <TriangleAlert className="size-3 text-sla-warn" /> : null}
          <span className="tabular-nums text-xs text-muted-foreground">
            {formatValue(dim.actor_value, dim.unit)}
          </span>
        </span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-muted">
        <div
          className="absolute inset-y-0 rounded-full bg-muted-foreground/25"
          style={{ left: `${boxLeft}%`, right: `${100 - boxRight}%` }}
        />
        <div
          className="absolute top-1/2 h-2.5 w-0.5 -translate-y-1/2 rounded bg-primary"
          style={{ left: pos(d.median) }}
        />
        <div
          className={cn(
            'absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card',
            stats.beyondRiskyTail ? 'bg-severity-critical' : 'bg-severity-low',
          )}
          style={{ left: pos(dim.actor_value) }}
        />
      </div>
    </button>
  )
}

function PeerSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-44 w-full" />
      <div className="grid grid-cols-2 gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    </div>
  )
}

/**
 * Peer comparison (FRONTEND-10 · Blueprint Part 11 / Part 24.4). Anchors the actor's behaviour to
 * its peer group: for the selected dimension it plots the peer inter-quartile box, min/max whiskers,
 * median, a jittered sample cloud, and the actor's value marked as a distinct line with the z-score —
 * so "abnormal" is concrete, fair, and peer-relative rather than absolute.
 */
export function PeerComparison({ entityId }: { entityId: string }) {
  const query = useQuery({
    queryKey: queryKeys.entityPeers(entityId),
    queryFn: () => apiClient.getEntityPeers(entityId),
  })

  const dimensions = useMemo<PeerDimension[]>(() => query.data?.dimensions ?? [], [query.data])
  // Default to the first flagged dimension (the reason we're looking), else the first.
  const defaultKey = useMemo<string | undefined>(() => {
    const flagged = dimensions.find((dim) => dim.flagged)
    return (flagged ?? dimensions[0])?.key
  }, [dimensions])

  const [selectedKey, setSelectedKey] = useState<string | undefined>(undefined)
  const activeKey = selectedKey ?? defaultKey
  const active = dimensions.find((dim) => dim.key === activeKey) ?? dimensions[0]

  const flaggedCount = dimensions.filter((dim) => dim.flagged).length

  return (
    <Card>
      <CardHeader className="gap-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <ScaleIcon className="size-4 text-muted-foreground" />
            Peer comparison
          </CardTitle>
          {query.data ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Users className="size-3.5" />
              <span className="tabular-nums">
                {query.data.peer_group}
                {query.data.peer_count != null ? ` · n=${query.data.peer_count}` : ''}
              </span>
              {flaggedCount > 0 ? (
                <Badge variant="warning" className="gap-1">
                  <TriangleAlert className="size-3" />
                  {flaggedCount} flagged
                </Badge>
              ) : null}
            </div>
          ) : null}
        </div>
        <CardDescription>
          The actor measured against same-role / same-branch peers — abnormality is relative to this
          cohort, not an absolute threshold.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <QueryBoundary
          isLoading={query.isLoading}
          isError={query.isError}
          error={query.error}
          onRetry={() => void query.refetch()}
          skeleton={<PeerSkeleton />}
        >
          {dimensions.length === 0 || !active ? (
            <EmptyState
              icon={Users}
              title="No peer dimensions"
              description="No comparable peer-group metrics are available for this entity yet."
            />
          ) : (
            <div className="space-y-4">
              {/* Dimension selector + meta. */}
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="peer-dimension" className="text-xs text-muted-foreground">
                    Dimension
                  </Label>
                  <Select value={active.key} onValueChange={setSelectedKey}>
                    <SelectTrigger id="peer-dimension" className="w-64">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {dimensions.map((dim) => (
                        <SelectItem key={dim.key} value={dim.key}>
                          <span className="flex items-center gap-2">
                            {dim.flagged ? (
                              <TriangleAlert className="size-3 text-sla-warn" />
                            ) : null}
                            {dim.label || humanize(dim.key)}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <DimensionMeta dim={active} />
              </div>

              {active.description ? (
                <p className="text-xs text-muted-foreground">{active.description}</p>
              ) : null}

              {/* The distribution chart. */}
              <PeerComparisonLegend />
              <DimensionChart dim={active} />
              <ComparisonVerdict dim={active} />

              <Separator />

              {/* All dimensions at a glance. */}
              <div>
                <div className="mb-2 text-xs font-medium text-muted-foreground">
                  All dimensions ({dimensions.length})
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {dimensions.map((dim) => (
                    <DimensionRow
                      key={dim.key}
                      dim={dim}
                      active={dim.key === active.key}
                      onSelect={() => setSelectedKey(dim.key)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </QueryBoundary>
      </CardContent>
    </Card>
  )
}

/* ── Legend so the marks are unambiguous in an audit context ────────────────── */
function PeerComparisonLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.7rem] text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-3 w-5 rounded-sm border border-muted-foreground/50 bg-muted-foreground/15" />
        Peer IQR (p25–p75)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-3 w-0.5 bg-primary" />
        Peer median
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2 rounded-full bg-muted-foreground/45" />
        Peer sample
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-3 w-0.5 bg-severity-critical" />
        Actor value
      </span>
    </div>
  )
}

/* Re-export the distribution type for downstream consumers that import alongside the component. */
export type { PeerDistribution }
