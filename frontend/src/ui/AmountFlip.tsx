/**
 * AmountFlip / CountUp — animated numeric roll-ups (docs/ui/UI_UPLIFT.md §3).
 *
 * A ₹ figure or a plain count that rolls from its previous value to the next over ~700ms, easing out.
 * Under `prefers-reduced-motion` (or `durationMs={0}`) it snaps to the final value instantly. The DOM
 * always exposes the **final** value via `aria-label`, so screen readers and tests never see the
 * in-flight digits. Monospaced + tabular so the number doesn't jitter as it counts.
 */
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/cn'
import { formatINR, formatINRCompact, formatNumber } from '@/lib/format'
import { useReducedMotionSafe } from './motion'

/** rAF roll-up from the last committed value to `value`, easing out. Instant when disabled. */
function useCountUp(value: number, durationMs: number, enabled: boolean): number {
  const [display, setDisplay] = useState(value)
  const fromRef = useRef(value)
  const rafRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!enabled || durationMs <= 0) {
      fromRef.current = value
      setDisplay(value)
      return
    }
    const from = fromRef.current
    const start = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / durationMs)
      const eased = 1 - Math.pow(1 - p, 3) // easeOutCubic
      setDisplay(from + (value - from) * eased)
      if (p < 1) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        fromRef.current = value
      }
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current !== undefined) cancelAnimationFrame(rafRef.current)
    }
  }, [value, durationMs, enabled])

  return display
}

export interface CountUpProps {
  value: number
  decimals?: number
  durationMs?: number
  className?: string
  /** Optional formatter for the in-flight + final value (defaults to `toFixed(decimals)`). */
  format?: (n: number) => string
}

/** Generic integer/float roll-up. */
export function CountUp({
  value,
  decimals = 0,
  durationMs = 700,
  className,
  format,
}: CountUpProps) {
  const reduce = useReducedMotionSafe()
  const display = useCountUp(value, reduce ? 0 : durationMs, !reduce)
  const fmt = format ?? ((n: number) => n.toFixed(decimals))
  return (
    <span className={cn('tabular-nums slashed-zero', className)} aria-label={fmt(value)}>
      {fmt(display)}
    </span>
  )
}

export interface AmountFlipProps {
  value: number
  /** `inr` groups by lakh/crore (₹); `plain` is a grouped integer. */
  kind?: 'inr' | 'plain'
  /** Use the compact ₹-crore/lakh form (e.g. "₹1.2 Cr"). */
  compact?: boolean
  durationMs?: number
  className?: string
}

/** Monetary roll-up — Indian ₹ grouping, monospaced, tabular. */
export function AmountFlip({
  value,
  kind = 'inr',
  compact = false,
  durationMs = 700,
  className,
}: AmountFlipProps) {
  const reduce = useReducedMotionSafe()
  const display = useCountUp(value, reduce ? 0 : durationMs, !reduce)
  const render = (n: number) => {
    const r = Math.round(n)
    if (kind === 'plain') return formatNumber(r)
    return compact ? formatINRCompact(r) : formatINR(r)
  }
  return (
    <span
      className={cn('font-mono tabular-nums slashed-zero', className)}
      aria-label={render(value)}
    >
      {render(display)}
    </span>
  )
}
