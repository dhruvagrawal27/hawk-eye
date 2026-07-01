/**
 * Alert temporal heatmap (FRONTEND graph-investigation upgrade).
 *
 * A 7-day (Mon..Sun) × 24-hour grid: every cell counts the alerts whose `created_ts` falls in that
 * IST day-of-week / hour-of-day bucket. Cell *fill intensity* scales with the bucket's alert count
 * (relative to the busiest bucket); cell *hue* is the worst severity in the bucket, drawn from the
 * shared severity palette (lib/risk) so the heatmap speaks the same colour language as the rest of
 * the terminal. Hovering a cell surfaces its count; clicking calls `onCellClick(dow, hour)` so a
 * parent can drill into that slice. Time is bucketed in IST (Asia/Kolkata), matching lib/format.
 *
 * Pure CSS-grid + tokens — no Recharts, no SVG chrome, no hardcoded hex.
 */
import { useMemo } from 'react'
import { CalendarClock } from 'lucide-react'
import { cn } from '@/lib/cn'
import { RISK_VAR, riskLevel, type RiskLevel } from '@/lib/risk'
import { severityRank } from '@/lib/format'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import type { Alert, Severity } from '@/lib/types'

/** Mon..Sun, Monday-first to match the IST week the analysts read against. */
const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const

/** Hour columns the axis labels every 3rd hour (00, 03, …) so it stays legible at 24 wide. */
const HOURS = Array.from({ length: 24 }, (_, h) => h)

/** Legend swatches ordered worst → best so the worst case reads first. */
const LEGEND_LEVELS: { level: RiskLevel; label: string }[] = [
  { level: 'critical', label: 'Critical' },
  { level: 'high', label: 'High' },
  { level: 'medium', label: 'Medium' },
  { level: 'low', label: 'Low' },
]

interface Bucket {
  count: number
  /** Highest severity seen in this bucket (drives the cell hue). */
  worst: RiskLevel
  worstRank: number
}

/**
 * IST weekday/hour extractor. `Intl` with timeZone=Asia/Kolkata gives the wall-clock the analyst
 * sees (lib/format §Time), so an event at 23:45 UTC lands in the next IST day's 05:00 bucket.
 */
const istParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  weekday: 'short',
  hour: '2-digit',
  hour12: false,
})

const DOW_INDEX: Record<string, number> = {
  Mon: 0,
  Tue: 1,
  Wed: 2,
  Thu: 3,
  Fri: 4,
  Sat: 5,
  Sun: 6,
}

function istDowHour(iso: string): { dow: number; hour: number } | null {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  let dow = -1
  let hour = -1
  for (const part of istParts.formatToParts(d)) {
    if (part.type === 'weekday') dow = DOW_INDEX[part.value] ?? -1
    else if (part.type === 'hour') {
      // Intl can emit "24" for midnight under hour12:false — fold it back to 0.
      const h = Number(part.value)
      hour = h === 24 ? 0 : h
    }
  }
  return dow < 0 || hour < 0 ? null : { dow, hour }
}

export interface AlertHeatmapProps {
  alerts: Alert[]
  /** Fired with the clicked cell's (day-of-week 0=Mon, hour 0..23). */
  onCellClick?: (dow: number, hour: number) => void
  className?: string
}

export function AlertHeatmap({ alerts, onCellClick, className }: AlertHeatmapProps) {
  const { grid, max, total } = useMemo(() => {
    // grid[dow][hour]
    const g: Bucket[][] = DOW_LABELS.map(() =>
      HOURS.map(() => ({ count: 0, worst: 'flat' as RiskLevel, worstRank: 0 })),
    )
    let mx = 0
    let n = 0
    for (const alert of alerts) {
      const slot = istDowHour(alert.created_ts)
      if (!slot) continue
      const cell = g[slot.dow][slot.hour]
      cell.count += 1
      n += 1
      if (cell.count > mx) mx = cell.count
      const level = riskLevel(alert.severity)
      const rank = severityRank[alert.severity as Severity] ?? 0
      if (rank > cell.worstRank) {
        cell.worstRank = rank
        cell.worst = level
      }
    }
    return { grid: g, max: mx, total: n }
  }, [alerts])

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow className="flex items-center gap-1.5">
            <CalendarClock className="size-3" />
            Alert heatmap · IST
          </Eyebrow>
          <p className="mt-1 text-xs text-muted-foreground">
            When alerts land, by day &amp; hour. Intensity ∝ volume, hue = worst severity in the
            bucket.
          </p>
        </div>
        <Legend total={total} />
      </div>

      {/* Grid: a label gutter + 24 hour columns; one row per weekday. */}
      <div className="overflow-x-auto">
        <div className="min-w-[34rem]" style={{ ['--hm-gutter' as string]: '2.25rem' }}>
          {/* Hour axis (top) */}
          <div
            className="grid items-center"
            style={{ gridTemplateColumns: 'var(--hm-gutter) repeat(24, minmax(0, 1fr))' }}
          >
            <span aria-hidden />
            {HOURS.map((h) => (
              <span
                key={h}
                className="text-center font-mono text-[0.5rem] tabular-nums text-muted-foreground"
              >
                {h % 3 === 0 ? String(h).padStart(2, '0') : ''}
              </span>
            ))}
          </div>

          {DOW_LABELS.map((label, dow) => (
            <div
              key={label}
              className="grid items-center"
              style={{
                gridTemplateColumns: 'var(--hm-gutter) repeat(24, minmax(0, 1fr))',
              }}
            >
              <span className="pr-2 text-right font-mono text-2xs uppercase tracking-wider text-muted-foreground">
                {label}
              </span>
              {HOURS.map((hour) => (
                <HeatCell
                  key={hour}
                  bucket={grid[dow][hour]}
                  max={max}
                  dow={dow}
                  dowLabel={label}
                  hour={hour}
                  onClick={onCellClick}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    </Surface>
  )
}

function HeatCell({
  bucket,
  max,
  dow,
  dowLabel,
  hour,
  onClick,
}: {
  bucket: Bucket
  max: number
  dow: number
  dowLabel: string
  hour: number
  onClick?: (dow: number, hour: number) => void
}) {
  const { count, worst } = bucket
  // Empty buckets read as a faint inset slot, not a coloured cell.
  const intensity = max > 0 && count > 0 ? 0.18 + 0.82 * (count / max) : 0
  const hh = String(hour).padStart(2, '0')
  const title =
    count > 0
      ? `${dowLabel} ${hh}:00–${hh}:59 IST · ${count} alert${count === 1 ? '' : 's'} · worst ${worst}`
      : `${dowLabel} ${hh}:00–${hh}:59 IST · no alerts`
  const interactive = Boolean(onClick)

  const style =
    count > 0
      ? {
          backgroundColor: `hsl(${RISK_VAR[worst]} / ${intensity.toFixed(3)})`,
          boxShadow: `inset 0 0 0 1px hsl(${RISK_VAR[worst]} / ${(intensity * 0.5).toFixed(3)})`,
        }
      : undefined

  return (
    <button
      type="button"
      disabled={!interactive}
      onClick={interactive ? () => onClick?.(dow, hour) : undefined}
      title={title}
      aria-label={title}
      className={cn(
        // Fixed, compact row height (was `aspect-square`, which ballooned the grid to ~380px of
        // mostly-empty cells on wide screens). Fills the column width; stays short on any viewport.
        'h-4 w-full rounded-[3px] border border-border/40 bg-muted/20 transition-colors sm:h-5',
        interactive && 'focus-ring hover:border-foreground/40',
        !interactive && 'cursor-default',
      )}
      style={style}
    >
      <span className="sr-only">{title}</span>
    </button>
  )
}

function Legend({ total }: { total: number }) {
  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex items-center gap-2">
        {LEGEND_LEVELS.map(({ level, label }) => (
          <span key={level} className="flex items-center gap-1" title={label}>
            <span
              className="size-2.5 rounded-[3px]"
              style={{ backgroundColor: `hsl(${RISK_VAR[level]} / 0.85)` }}
              aria-hidden
            />
            <span className="font-mono text-2xs text-muted-foreground">{label}</span>
          </span>
        ))}
      </div>
      <span className="font-mono text-2xs tabular-nums text-muted-foreground">
        {total} alert{total === 1 ? '' : 's'} · darker = busier
      </span>
    </div>
  )
}
