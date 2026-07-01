/**
 * SlaRing — RBI ≤30-day TAT countdown ring (docs/ui/UI_UPLIFT.md §3).
 *
 * A compact ring that drains as the SLA window closes, coloured by the SLA band (ok → warn → urgent →
 * breached) from the single-source `slaInfo()`. The centre shows the compact "29d left" / "Breached 2d"
 * label. Pure SVG; the drain respects reduced motion.
 */
import { cn } from '@/lib/cn'
import { slaInfo, type SlaState } from '@/lib/format'

const SLA_VAR: Record<SlaState, string> = {
  ok: 'var(--sla-ok)',
  warn: 'var(--sla-warn)',
  urgent: 'var(--sla-urgent)',
  breached: 'var(--sla-breached)',
}

/** Total SLA window used to normalise the ring fill (RBI 30-day default). */
const WINDOW_MS = 30 * 86_400_000

export interface SlaRingProps {
  /** ISO/Date SLA due timestamp (`sla_due_ts`). */
  dueTs: string | number | Date
  /** Injectable clock for tests. */
  now?: Date
  /** Diameter in px. */
  size?: number
  /** Show the compact remaining-time label under the ring. */
  showLabel?: boolean
  className?: string
}

export function SlaRing({ dueTs, now, size = 40, showLabel = true, className }: SlaRingProps) {
  const info = slaInfo(dueTs, now)
  const color = `hsl(${SLA_VAR[info.state]})`

  const stroke = Math.max(3, Math.round(size / 10))
  const center = size / 2
  const radius = (size - stroke) / 2
  const circ = 2 * Math.PI * radius

  // Fraction of the window remaining (drains toward 0). Breached → empty ring.
  const remainingFrac = info.breached ? 0 : Math.max(0, Math.min(1, info.msRemaining / WINDOW_MS))
  const filled = circ * remainingFrac

  return (
    <div
      className={cn('inline-flex flex-col items-center gap-1', className)}
      data-sla-state={info.state}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="block -rotate-90"
        >
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="hsl(var(--muted))"
            strokeWidth={stroke}
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ}`}
            className="motion-safe:transition-[stroke-dasharray] motion-safe:duration-500 motion-safe:ease-out"
          />
        </svg>
        {info.state === 'urgent' || info.breached ? (
          <span
            className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full motion-safe:animate-pulse-urgent"
            style={{ backgroundColor: color }}
            aria-hidden
          />
        ) : null}
      </div>
      {showLabel ? (
        <span
          className="font-mono text-2xs tabular-nums"
          style={{ color }}
          aria-label={`SLA ${info.label}`}
        >
          {info.label}
        </span>
      ) : null}
    </div>
  )
}
