/**
 * TopStatusBar — the persistent Bloomberg status strip at the very top of the app shell.
 *
 * A single h-7 mono-uppercase tape: product mark + LIVE/IDLE indicator on the left, a decoupled KPI
 * strip (ALERTS-OPEN · HIGH-RISK · EVENTS · EPS) in the centre/right, service-health dots for
 * {api, stream, llm}, and an isolated <LiveClock/> leaf far right.
 *
 * Re-render discipline (study gotchas):
 *  - ONE stream subscription, owned by useEventRate (EPS + live), never resubscribed per tick.
 *  - KPI counts come from a 5s-polled useQuery(['alerts']) — decoupled from the stream entirely.
 *  - realtime.status() isn't reactive, so EVENTS is sampled on a single 1s interval (also the
 *    `running` source for the stream dot) — not via a stream subscription.
 *  - <LiveClock/> is its own React.memo leaf with its OWN 1s tick, so the seconds digit re-renders
 *    that 14-char span and nothing else in the bar.
 */
import * as React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, CircleDot, Radio, ShieldAlert, Sparkles } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { realtime } from '@/lib/realtime'
import { useEventRate } from '@/hooks/useRealtime'
import { formatISTTime } from '@/lib/format'
import { cn } from '@/lib/cn'

/* ── service-health dot ──────────────────────────────────────────────────── */

type Health = 'ok' | 'degraded' | 'down'

const HEALTH_DOT: Record<Health, string> = {
  ok: 'text-[hsl(var(--sla-ok))]',
  degraded: 'text-[hsl(var(--sla-warn))]',
  down: 'text-risk-high',
}

function HealthDot({ label, state }: { label: string; state: Health }) {
  return (
    <span className="inline-flex items-center gap-1" title={`${label.toUpperCase()}: ${state}`}>
      <CircleDot
        className={cn(
          'size-2.5',
          HEALTH_DOT[state],
          state === 'down' && 'motion-safe:animate-pulse-soft',
        )}
        aria-hidden
      />
      <span className="text-muted-foreground">{label}</span>
    </span>
  )
}

/* ── KPI cell ────────────────────────────────────────────────────────────── */

function Kpi({
  icon,
  label,
  value,
  valueClassName,
}: {
  icon?: React.ReactNode
  label: string
  value: React.ReactNode
  valueClassName?: string
}) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {icon}
      <span className="text-muted-foreground">{label}</span>
      <span className={cn('tabular-nums text-foreground', valueClassName)}>{value}</span>
    </span>
  )
}

/* ── isolated clock leaf (the only thing ticking every second) ───────────── */

const LiveClock = React.memo(function LiveClock() {
  const [now, setNow] = React.useState(() => Date.now())
  React.useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <span className="tabular-nums text-ticker" aria-label="Current time">
      {formatISTTime(now)} IST
    </span>
  )
})

/* ── status bar ──────────────────────────────────────────────────────────── */

const SEP = (
  <span className="text-border" aria-hidden>
    ·
  </span>
)

export function TopStatusBar() {
  // EPS + liveness off the shared stream (one subscription for the whole bar).
  const { eps, live } = useEventRate(60)

  // Decoupled 5s poll → ALERTS-OPEN / HIGH-RISK, and doubles as the `api` health ping.
  const alertsQuery = useQuery({
    queryKey: ['alerts'],
    queryFn: () => apiClient.listAlerts({ page_size: 200 }),
    refetchInterval: 5000,
    refetchIntervalInBackground: true,
  })

  const { openCount, highCount } = React.useMemo(() => {
    const items = alertsQuery.data?.items ?? []
    let open = 0
    let high = 0
    for (const a of items) {
      const isClosed =
        a.status === 'closed' ||
        a.status === 'confirmed_fraud' ||
        a.status === 'false_positive' ||
        a.status === 'inconclusive'
      if (!isClosed) open++
      if (a.severity === 'high' || a.severity === 'critical') high++
    }
    return { openCount: open, highCount: high }
  }, [alertsQuery.data])

  // realtime.status() is a plain getter (not reactive) → sample it on ONE 1s interval for the
  // running flag (stream dot) and the cumulative EVENTS counter. No extra stream subscription.
  const [status, setStatus] = React.useState(() => realtime.status())
  React.useEffect(() => {
    const id = setInterval(() => setStatus(realtime.status()), 1000)
    return () => clearInterval(id)
  }, [])

  const running = status.running || live
  const apiState: Health = alertsQuery.isError ? 'down' : alertsQuery.isSuccess ? 'ok' : 'degraded'
  const streamState: Health = status.running ? 'ok' : 'down'
  const llmState: Health = 'ok' // static ok (no provider seam wired to the bar)

  return (
    <header
      className="flex h-7 w-full select-none items-center gap-3 overflow-hidden border-b border-border bg-card/80 px-3 font-mono text-2xs font-medium uppercase tracking-wider text-muted-foreground"
      role="status"
      aria-label="System status"
    >
      {/* ── left: product mark + live/idle ─────────────────────────────── */}
      <span className="inline-flex items-center gap-1.5 whitespace-nowrap font-semibold tracking-widest text-foreground">
        <Radio className="size-3 text-ticker" aria-hidden />
        HAWKEYE
      </span>

      <span
        className={cn(
          'inline-flex items-center gap-1.5 whitespace-nowrap',
          running ? 'text-ticker' : 'text-muted-foreground',
        )}
      >
        <span
          className={cn(
            'inline-block size-2 rounded-full',
            running ? 'bg-ticker motion-safe:animate-pulse-soft' : 'bg-risk-flat',
          )}
          aria-hidden
        />
        {running ? 'LIVE' : 'IDLE'}
      </span>

      {/* ── centre/right: KPI strip ────────────────────────────────────── */}
      <div className="ml-auto flex items-center gap-3 whitespace-nowrap">
        <Kpi
          icon={<ShieldAlert className="size-3 text-risk-medium" aria-hidden />}
          label="Alerts-Open"
          value={alertsQuery.isPending ? '—' : openCount}
        />
        {SEP}
        <Kpi
          icon={<ShieldAlert className="size-3 text-risk-high" aria-hidden />}
          label="High-Risk"
          value={alertsQuery.isPending ? '—' : highCount}
          valueClassName={highCount > 0 ? 'text-risk-high' : undefined}
        />
        {SEP}
        <Kpi
          icon={<Activity className="size-3 text-ticker" aria-hidden />}
          label="Events"
          value={status.eventsPublished.toLocaleString('en-IN')}
        />
        {SEP}
        <Kpi
          icon={<Sparkles className="size-3 text-ticker" aria-hidden />}
          label="EPS"
          value={eps.toFixed(1)}
          valueClassName="text-ticker"
        />
      </div>

      {/* ── service-health dots ────────────────────────────────────────── */}
      <div className="hidden items-center gap-2.5 border-l border-border pl-3 md:flex">
        <HealthDot label="api" state={apiState} />
        <HealthDot label="stream" state={streamState} />
        <HealthDot label="llm" state={llmState} />
      </div>

      {/* ── far right: isolated clock leaf ─────────────────────────────── */}
      <div className="border-l border-border pl-3">
        <LiveClock />
      </div>
    </header>
  )
}
