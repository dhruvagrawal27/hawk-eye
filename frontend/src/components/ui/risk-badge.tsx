import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'
import { riskLevel, type RiskLevel } from '@/lib/risk'

/**
 * One severity badge for the whole console (study S3). Drives off the single `risk` palette.
 * Pass an explicit `level`, or a numeric `score` (0–100) to band automatically. `critical`
 * pulses (gated by prefers-reduced-motion via the `motion-safe:` variant).
 */
const riskBadgeVariants = cva(
  'inline-flex items-center gap-1 rounded border font-mono uppercase leading-none tracking-wide',
  {
    variants: {
      level: {
        low: 'border-risk-low/40 bg-risk-low/10 text-risk-low',
        medium: 'border-risk-medium/40 bg-risk-medium/10 text-risk-medium',
        high: 'border-risk-high/50 bg-risk-high/15 text-risk-high',
        critical:
          'border-risk-critical/60 bg-risk-critical/15 text-risk-critical motion-safe:animate-pulse-urgent',
        flat: 'border-risk-flat/40 bg-risk-flat/10 text-risk-flat',
      },
      size: {
        sm: 'px-1.5 py-0.5 text-2xs',
        md: 'px-2 py-0.5 text-xs',
        lg: 'px-2.5 py-1 text-sm',
      },
    },
    defaultVariants: { level: 'flat', size: 'sm' },
  },
)

export interface RiskBadgeProps
  extends Omit<React.HTMLAttributes<HTMLSpanElement>, 'children'>,
    Omit<VariantProps<typeof riskBadgeVariants>, 'level'> {
  /** Explicit band, or omit and pass `score`. */
  level?: RiskLevel
  /** 0–100 risk score; banded automatically when `level` is absent. */
  score?: number
  /** Override the label (defaults to the band name, or the score when given). */
  label?: string
}

export function RiskBadge({ level, score, size, label, className, ...props }: RiskBadgeProps) {
  const resolved: RiskLevel = level ?? riskLevel(score)
  const text = label ?? (score != null ? String(Math.round(score)) : resolved)
  return (
    <span className={cn(riskBadgeVariants({ level: resolved, size }), className)} {...props}>
      {text}
    </span>
  )
}

export { riskBadgeVariants }
