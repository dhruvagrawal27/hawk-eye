import * as React from 'react'
import { riskColor } from '@/lib/risk'
import { cn } from '@/lib/cn'

/**
 * Bespoke SVG arc gauge (NOT recharts): a 270° background track with a foreground arc whose
 * sweep is proportional to the 0–100 score and whose stroke is the single-source riskColor().
 * A centered big tabular-mono number (the score) sits over the dial, with an optional small
 * uppercase label beneath it.
 *
 * Implementation is a stroke-dashoffset circle rotated so the 90° gap sits at the bottom, which
 * keeps it pure SVG (no path arithmetic) and lets the sweep animate via a single dashoffset
 * transition. Respects prefers-reduced-motion: no draw animation when reduced.
 *
 * Pure: no deps beyond react + lib/risk + cn.
 */

const SIZES = {
  sm: { px: 64, stroke: 6, fontClass: 'text-sm', labelClass: 'text-3xs' },
  md: { px: 104, stroke: 9, fontClass: 'text-2xl', labelClass: 'text-2xs' },
  lg: { px: 150, stroke: 12, fontClass: 'text-4xl', labelClass: 'text-xs' },
} as const

export type ScoreGaugeSize = keyof typeof SIZES

export interface ScoreGaugeProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Risk score, 0–100. Clamped to that range. */
  score: number
  size?: ScoreGaugeSize
  /** Optional small uppercase caption rendered under the number. */
  label?: string
}

/** Fraction of the full circle that the visible track covers (270° of 360°). */
const ARC_FRACTION = 270 / 360

export function ScoreGauge({ score, size = 'md', label, className, ...props }: ScoreGaugeProps) {
  const { px, stroke, fontClass, labelClass } = SIZES[size]

  const safe = Number.isFinite(score) ? Math.min(100, Math.max(0, score)) : 0
  const color = riskColor(safe)

  // Geometry: circle inset by half the stroke so the line never clips the viewBox.
  const radius = (px - stroke) / 2
  const center = px / 2
  const circumference = 2 * Math.PI * radius
  const trackLen = circumference * ARC_FRACTION

  // Foreground dash: a `filled` segment followed by a gap large enough to hide the rest.
  const filled = trackLen * (safe / 100)

  // Rotate so the 270° arc is centered with its gap at the bottom: a circle's dash starts at
  // 3 o'clock and runs clockwise. Offsetting by 135° puts the start at the lower-left, sweeping
  // up over the top to the lower-right — leaving a symmetric 90° gap at the bottom.
  const rotation = 90 + (360 - 270) / 2 // = 135°

  return (
    <div
      className={cn('relative inline-flex flex-col items-center justify-center', className)}
      style={{ width: px, height: px }}
      role="img"
      aria-label={
        label ? `${label}: ${Math.round(safe)} of 100` : `Score ${Math.round(safe)} of 100`
      }
      {...props}
    >
      <svg
        width={px}
        height={px}
        viewBox={`0 0 ${px} ${px}`}
        className="-rotate-90 block"
        // The -rotate-90 above orients SVG 0° to the top; the inner group adds the gap offset.
        aria-hidden="true"
      >
        <g transform={`rotate(${rotation} ${center} ${center})`}>
          {/* Background track */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${trackLen} ${circumference}`}
          />
          {/* Foreground arc — sweep ∝ score, colour = riskColor(score) */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            // Gentle draw transition; suppressed under prefers-reduced-motion via the utility class.
            className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-500 motion-safe:ease-out"
          />
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn('font-mono font-semibold leading-none tabular-nums', fontClass)}
          style={{ color }}
        >
          {Math.round(safe)}
        </span>
        {label ? (
          <span
            className={cn(
              'mt-0.5 font-mono font-medium uppercase tracking-widest text-muted-foreground',
              labelClass,
            )}
          >
            {label}
          </span>
        ) : null}
      </div>
    </div>
  )
}
