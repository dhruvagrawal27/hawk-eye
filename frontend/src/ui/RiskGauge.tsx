/**
 * RiskGauge — the signature risk dial (docs/ui/UI_UPLIFT.md §3).
 *
 * A 270° arc meter over a 0–`max` score, stroked in the single-source risk-ramp colour, with an
 * optional concentric **confidence** ring (dashed = "how sure") and an animated roll-up headline
 * number. Richer sibling of `components/ui/score-gauge` (that one stays for compact inline use).
 * Pure SVG (no path math, no chart dep); the arc draw + number roll-up both respect reduced motion.
 *
 * ALERT-ONLY: this renders a score. It offers no block/classify affordance — decisions live in the
 * feature screens behind RBAC/SoD.
 */
import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/cn'
import { riskColor, riskLevel } from '@/lib/risk'
import { CountUp } from './AmountFlip'

const SIZES = {
  sm: { px: 72, stroke: 6, ring: 3, fontClass: 'text-base', labelClass: 'text-3xs' },
  md: { px: 116, stroke: 9, ring: 4, fontClass: 'text-3xl', labelClass: 'text-2xs' },
  lg: { px: 168, stroke: 12, ring: 5, fontClass: 'text-5xl', labelClass: 'text-xs' },
} as const

export type RiskGaugeSize = keyof typeof SIZES

export interface RiskGaugeProps extends HTMLAttributes<HTMLDivElement> {
  /** Score, 0–`max`. Clamped. */
  score: number
  max?: number
  /** Model confidence 0–1 — drawn as a dashed inner ring when provided. */
  confidence?: number
  size?: RiskGaugeSize
  /** Small uppercase caption under the number. */
  label?: string
  /** Animate the headline number rolling up on mount/change (default true). */
  animateNumber?: boolean
}

const ARC_FRACTION = 270 / 360

export function RiskGauge({
  score,
  max = 100,
  confidence,
  size = 'md',
  label,
  animateNumber = true,
  className,
  ...props
}: RiskGaugeProps) {
  const { px, stroke, ring, fontClass, labelClass } = SIZES[size]
  const safeMax = max > 0 ? max : 100
  const safe = Number.isFinite(score) ? Math.min(safeMax, Math.max(0, score)) : 0
  const frac = safe / safeMax
  // Colour by normalised 0–100 so the ramp cut-points hold for any `max`.
  const color = riskColor((frac * 100) as number)
  const level = riskLevel((frac * 100) as number)

  const center = px / 2
  const radius = (px - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const trackLen = circumference * ARC_FRACTION
  const filled = trackLen * frac
  const rotation = 135 // symmetric 90° gap at the bottom (see score-gauge)

  const hasConf = typeof confidence === 'number' && Number.isFinite(confidence)
  const conf = hasConf ? Math.min(1, Math.max(0, confidence as number)) : 0
  const ringRadius = radius - stroke / 2 - ring - 2
  const ringCirc = 2 * Math.PI * ringRadius
  const ringTrack = ringCirc * ARC_FRACTION
  const ringFilled = ringTrack * conf

  const round = safeMax === 100 ? Math.round(safe) : Number(safe.toFixed(safe < 10 ? 1 : 0))

  return (
    <div
      className={cn('relative inline-flex flex-col items-center justify-center', className)}
      style={{ width: px, height: px }}
      role="img"
      aria-label={
        (label ? `${label}: ` : 'Risk ') +
        `${round} of ${safeMax}` +
        (hasConf ? `, confidence ${Math.round(conf * 100)}%` : '') +
        `, ${level} band`
      }
      {...props}
    >
      <svg
        width={px}
        height={px}
        viewBox={`0 0 ${px} ${px}`}
        className="block -rotate-90"
        aria-hidden="true"
      >
        <g transform={`rotate(${rotation} ${center} ${center})`}>
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
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circumference}`}
            className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-500 motion-safe:ease-out"
          />
          {hasConf ? (
            <>
              {/* Confidence ring: faint track + a thinner arc whose length ∝ confidence. */}
              <circle
                cx={center}
                cy={center}
                r={ringRadius}
                fill="none"
                stroke="hsl(var(--border))"
                strokeWidth={ring}
                strokeDasharray={`${ringTrack} ${ringCirc}`}
              />
              <circle
                cx={center}
                cy={center}
                r={ringRadius}
                fill="none"
                stroke="hsl(var(--muted-foreground))"
                strokeWidth={ring}
                strokeLinecap="round"
                strokeDasharray={`${ringFilled} ${ringCirc}`}
                className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-500 motion-safe:ease-out"
              />
            </>
          ) : null}
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <span
          className={cn('font-mono font-semibold leading-none tabular-nums', fontClass)}
          style={{ color }}
        >
          {animateNumber ? (
            <CountUp value={round} decimals={safeMax === 100 ? 0 : round % 1 === 0 ? 0 : 1} />
          ) : (
            round
          )}
        </span>
        {label ? (
          <span
            className={cn(
              'mt-1 font-mono font-medium uppercase tracking-widest text-muted-foreground',
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
