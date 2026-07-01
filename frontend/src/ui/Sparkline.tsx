/**
 * Sparkline — inline trend line (docs/ui/UI_UPLIFT.md §3).
 *
 * A tiny dependency-free SVG line (optionally area-filled) for showing a series' shape inline — a
 * peer's 30-day amount trend, a score history, a velocity curve. Normalises to its own min/max so any
 * scale fits the box. No animation (it's a static glyph); safe to render in dense tables.
 */
import { cn } from '@/lib/cn'

export interface SparklineProps {
  points: number[]
  width?: number
  height?: number
  /** Stroke colour (any CSS colour / `hsl(var(--…))`). Defaults to the ink-teal accent. */
  stroke?: string
  /** Fill a faint area under the line. */
  area?: boolean
  strokeWidth?: number
  className?: string
  'aria-label'?: string
}

export function Sparkline({
  points,
  width = 96,
  height = 24,
  stroke = 'hsl(var(--primary))',
  area = false,
  strokeWidth = 1.5,
  className,
  'aria-label': ariaLabel,
}: SparklineProps) {
  const pad = strokeWidth + 1
  const n = points.length
  if (n === 0) {
    return <svg width={width} height={height} className={className} aria-hidden />
  }

  const min = Math.min(...points)
  const max = Math.max(...points)
  const span = max - min || 1
  const innerW = width - pad * 2
  const innerH = height - pad * 2

  const x = (i: number) => pad + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW)
  // SVG y grows downward → invert so higher values sit higher.
  const y = (v: number) => pad + innerH - ((v - min) / span) * innerH

  const line = points
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(2)} ${y(v).toFixed(2)}`)
    .join(' ')
  const areaPath = `${line} L${x(n - 1).toFixed(2)} ${(height - pad).toFixed(2)} L${x(0).toFixed(2)} ${(height - pad).toFixed(2)} Z`

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn('block overflow-visible', className)}
      role="img"
      aria-label={ariaLabel ?? `Trend of ${n} points`}
      preserveAspectRatio="none"
    >
      {area ? <path d={areaPath} fill={stroke} opacity={0.12} stroke="none" /> : null}
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* End marker — the "now" dot. */}
      <circle cx={x(n - 1)} cy={y(points[n - 1])} r={strokeWidth + 0.5} fill={stroke} />
    </svg>
  )
}
