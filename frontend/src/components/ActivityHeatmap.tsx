/**
 * Entity activity heatmap (7-day × 24-hour, IST) — surfaces *when* an actor is active and how much
 * of that activity is **off-hours**, a first-order insider signal (rogue traders, exfil-before-
 * resignation, DBAs working the night batch legitimately vs. an ops maker firing payments at 02:14).
 *
 * One cell per IST weekday × hour. Intensity ∝ the bucket's event count (relative to the busiest
 * bucket); the hue is off-hours (warm) vs. bank-hours (cool), so a cluster of night/weekend activity
 * reads instantly. The header stat is the off-hours share of all activity. Pure CSS-grid + tokens.
 */
import { useMemo } from 'react'
import { CalendarClock, Moon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const
const HOURS = Array.from({ length: 24 }, (_, h) => h)

const DOW_INDEX: Record<string, number> = {
  Mon: 0,
  Tue: 1,
  Wed: 2,
  Thu: 3,
  Fri: 4,
  Sat: 5,
  Sun: 6,
}
const istParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  weekday: 'short',
  hour: '2-digit',
  hour12: false,
})

function istDowHour(iso: string): { dow: number; hour: number } | null {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  let dow = -1
  let hour = -1
  for (const part of istParts.formatToParts(d)) {
    if (part.type === 'weekday') dow = DOW_INDEX[part.value] ?? -1
    else if (part.type === 'hour') {
      const h = Number(part.value)
      hour = h === 24 ? 0 : h
    }
  }
  return dow < 0 || hour < 0 ? null : { dow, hour }
}

/** A (dow,hour) bucket is off-hours outside IST bank hours: weekend, or before 08:00 / from 20:00. */
export function bucketIsOffHours(dow: number, hour: number): boolean {
  return dow >= 5 || hour < 8 || hour >= 20
}

export interface ActivityPoint {
  ts: string
  offHours?: boolean
}

export function ActivityHeatmap({
  points,
  className,
}: {
  points: ActivityPoint[]
  className?: string
}) {
  const { grid, max, total, offHoursCount } = useMemo(() => {
    const g: number[][] = DOW_LABELS.map(() => HOURS.map(() => 0))
    let mx = 0
    let n = 0
    let off = 0
    for (const p of points) {
      const slot = istDowHour(p.ts)
      if (!slot) continue
      g[slot.dow][slot.hour] += 1
      n += 1
      if (g[slot.dow][slot.hour] > mx) mx = g[slot.dow][slot.hour]
      const isOff = p.offHours ?? bucketIsOffHours(slot.dow, slot.hour)
      if (isOff) off += 1
    }
    return { grid: g, max: mx, total: n, offHoursCount: off }
  }, [points])

  const offShare = total > 0 ? offHoursCount / total : 0

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Eyebrow className="flex items-center gap-1.5">
            <CalendarClock className="size-3" />
            Activity heatmap · IST
          </Eyebrow>
          <p className="mt-1 text-xs text-muted-foreground">
            When this actor is active, by day &amp; hour. Warm = off-hours; intensity ∝ volume.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-mono text-2xs tabular-nums',
              offShare >= 0.3
                ? 'bg-severity-medium/15 text-severity-medium'
                : 'bg-muted/40 text-muted-foreground',
            )}
          >
            <Moon className="size-3" />
            {Math.round(offShare * 100)}% off-hours
          </span>
          <span className="font-mono text-2xs tabular-nums text-muted-foreground">
            {total} event{total === 1 ? '' : 's'}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[34rem]" style={{ ['--hm-gutter' as string]: '2.25rem' }}>
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
              style={{ gridTemplateColumns: 'var(--hm-gutter) repeat(24, minmax(0, 1fr))' }}
            >
              <span className="pr-2 text-right font-mono text-2xs uppercase tracking-wider text-muted-foreground">
                {label}
              </span>
              {HOURS.map((hour) => {
                const count = grid[dow][hour]
                const off = bucketIsOffHours(dow, hour)
                const intensity = max > 0 && count > 0 ? 0.18 + 0.82 * (count / max) : 0
                const hueVar = off ? '--severity-medium' : '--primary'
                const hh = String(hour).padStart(2, '0')
                const title =
                  count > 0
                    ? `${label} ${hh}:00–${hh}:59 IST · ${count} event${count === 1 ? '' : 's'}${off ? ' · off-hours' : ''}`
                    : `${label} ${hh}:00–${hh}:59 IST · no activity${off ? ' · off-hours' : ''}`
                return (
                  <div
                    key={hour}
                    title={title}
                    aria-label={title}
                    className="aspect-square w-full rounded-[3px] border border-border/40 bg-muted/20"
                    style={
                      count > 0
                        ? { backgroundColor: `hsl(var(${hueVar}) / ${intensity.toFixed(3)})` }
                        : undefined
                    }
                  >
                    <span className="sr-only">{title}</span>
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4 text-2xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="size-2.5 rounded-[3px]"
            style={{ backgroundColor: 'hsl(var(--primary) / 0.8)' }}
            aria-hidden
          />
          bank hours
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="size-2.5 rounded-[3px]"
            style={{ backgroundColor: 'hsl(var(--severity-medium) / 0.8)' }}
            aria-hidden
          />
          off-hours (Mon–Fri 20:00–08:00 · weekends)
        </span>
      </div>
    </Surface>
  )
}
