import { useEffect, useState } from 'react'
import { AlarmClock, AlarmClockOff, Clock } from 'lucide-react'
import { cn } from '@/lib/cn'
import { slaInfo, formatISTDate } from '@/lib/format'
import { slaStateClass } from '@/components/badges'

/**
 * SLA/TAT countdown from `sla_due_ts` (RBI ≤30-day examination window — Part 24.4 screen 2).
 * Colour-grades green → amber → red → breached and live-ticks every 30s so the queue and the alert
 * header stay consistent. `now` is injectable for deterministic tests.
 */
export function SlaTimer({
  dueTs,
  compact = false,
  showDate = false,
  className,
  now,
}: {
  dueTs: string
  compact?: boolean
  showDate?: boolean
  className?: string
  now?: Date
}) {
  const [, setTick] = useState(0)
  useEffect(() => {
    if (now) return // fixed clock (tests) — no ticking
    const id = setInterval(() => setTick((t) => t + 1), 30_000)
    return () => clearInterval(id)
  }, [now])

  const info = slaInfo(dueTs, now)
  const Icon = info.breached ? AlarmClockOff : info.state === 'ok' ? Clock : AlarmClock

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs font-medium tabular-nums',
        slaStateClass[info.state],
        info.state === 'urgent' && !compact && 'animate-pulse-urgent',
        className,
      )}
      title={`SLA due ${formatISTDate(dueTs)} — RBI ≤30-day examination window`}
      data-sla-state={info.state}
    >
      <Icon className="size-3.5" />
      {info.label}
      {showDate && !compact ? (
        <span className="text-muted-foreground">· {formatISTDate(dueTs)}</span>
      ) : null}
    </span>
  )
}
