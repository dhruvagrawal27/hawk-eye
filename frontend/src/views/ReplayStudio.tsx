/**
 * ReplayStudio (AGENT B — replay studio). A control surface for the realtime stream seam, for
 * managers / executives / admins who want to drive the demo book of events: front-load a high-risk
 * "mule burst", run steady traffic, inject an extra burst, or stop the stream — and watch the live
 * counters + tape + ingestion-rate chart respond.
 *
 * The stream is the singleton `realtime` source (one producer, fanned out to every widget — see
 * lib/realtime.ts). Controls call `realtime.start('mule_burst') / stop() / injectBurst()`; the live
 * counters poll `realtime.status()` on a 1.5s interval (the status snapshot isn't a React store, so a
 * cheap poll is the right read), while the embedded <LiveEventTape> and <EventRateChart> subscribe to
 * the same stream for their high-frequency state. Swapping the mock generator for the real WebSocket
 * is the one-line change at the bottom of lib/realtime.ts — this surface doesn't change.
 */
import { useEffect, useState } from 'react'
import { Activity, Play, Radio, Siren, Square, Zap } from 'lucide-react'
import { realtime, type RealtimeStatus, type RealtimeTick } from '@/lib/realtime'
import { useRealtimeSubscription } from '@/hooks/useRealtime'
import { formatINRCompact, formatISTTime } from '@/lib/format'
import { PageHeader } from '@/components/PageHeader'
import { LiveEventTape } from '@/components/realtime/LiveEventTape'
import { EventRateChart } from '@/components/charts/EventRateChart'
import { Surface } from '@/components/ui/surface'
import { Stat } from '@/components/ui/stat'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { EventTicker, RouteTransition, type TickerItem } from '@/ui'

const POLL_MS = 1500
/** Calm split-flap tape holds only a shallow window — it's ambient context, not the main tape. */
const TICKER_CAP = 12

/** Keep the tokenized prefix + last 2 chars, dot out the middle — never surfaces a raw id. */
function maskEmployee(id: string): string {
  const dash = id.indexOf('-')
  if (dash < 0 || dash >= id.length - 1) return id
  const prefix = id.slice(0, dash + 1)
  const body = id.slice(dash + 1)
  if (body.length <= 2) return `${prefix}${body}`
  return `${prefix}••${body.slice(-2)}`
}

/** Map a scored realtime tick to the EventTicker's presentational TickerItem shape. */
function tickToTickerItem(tick: RealtimeTick): TickerItem {
  const text = tick.top_signal
    ? tick.top_signal.replace(/_/g, ' ').toLowerCase()
    : `${tick.txn_type} · ${tick.channel}`
  return {
    id: String(tick.tick_id),
    ts: formatISTTime(tick.ts),
    actor: maskEmployee(tick.employee_id),
    text: tick.is_after_hours ? `${text} · off-hours` : text,
    level: tick.risk_level,
    amount: formatINRCompact(tick.amount),
  }
}

/** Humanize the source mode for the status pill (idle / steady / mule_burst / ws). */
function modeLabel(mode: string): string {
  switch (mode) {
    case 'mule_burst':
      return 'Mule burst'
    case 'steady':
      return 'Steady'
    case 'idle':
      return 'Idle'
    case 'ws':
      return 'Live socket'
    default:
      return mode
  }
}

export function ReplayStudio() {
  const [status, setStatus] = useState<RealtimeStatus>(() => realtime.status())

  // The status snapshot lives in the singleton (not React state) — poll it on a light interval.
  useEffect(() => {
    const id = setInterval(() => setStatus(realtime.status()), POLL_MS)
    return () => clearInterval(id)
  }, [])

  // Calm split-flap tape — a shallow, newest-first window off the same singleton stream. State stays
  // LOCAL to this view (one subscription) so a tick re-renders only the tape, never the tree.
  const [ticker, setTicker] = useState<TickerItem[]>([])
  useRealtimeSubscription((m) => {
    if (m.type !== 'event.scored') return
    setTicker((prev) => [tickToTickerItem(m), ...prev].slice(0, TICKER_CAP))
  })

  // Reflect a control action immediately rather than waiting up to POLL_MS for the next tick.
  const sync = () => setStatus(realtime.status())

  const running = status.running

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<Radio className="size-5" />}
        title="Replay studio"
        description="Drive the realtime detection stream — front-load a high-risk mule burst, run steady traffic, or inject a burst — and watch alerts fire live. One singleton source feeds every widget."
        actions={
          <Badge
            variant={running ? 'success' : 'muted'}
            className="gap-1.5 font-mono uppercase tabular-nums"
          >
            <span
              className={
                running
                  ? 'inline-block size-1.5 rounded-full bg-current motion-safe:animate-pulse-soft'
                  : 'inline-block size-1.5 rounded-full bg-current'
              }
              aria-hidden
            />
            {running ? 'Streaming' : 'Stopped'} · {modeLabel(status.mode)}
          </Badge>
        }
      />

      {/* Transport controls. */}
      <Surface tone="actionable" className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          onClick={() => {
            realtime.start('mule_burst')
            sync()
          }}
          disabled={running}
        >
          <Play className="size-4" />
          Start mule burst
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            realtime.injectBurst()
            sync()
          }}
        >
          <Zap className="size-4 text-severity-high" />
          Inject burst
        </Button>
        <Button
          type="button"
          variant="destructive"
          onClick={() => {
            realtime.stop()
            sync()
          }}
          disabled={!running}
        >
          <Square className="size-4" />
          Stop
        </Button>

        <p className="ml-auto max-w-md text-2xs text-muted-foreground">
          Controls drive the shared mock generator. Nothing here blocks or actions an account — it
          only replays scored events into the console (alert-only system).
        </p>
      </Surface>

      {/* Live counters from realtime.status(). */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Surface pad="md">
          <Stat
            icon={<Activity className="size-3.5 text-ticker" />}
            label="Events published"
            value={status.eventsPublished.toLocaleString('en-IN')}
            hint="cumulative this session"
          />
        </Surface>
        <Surface pad="md">
          <Stat
            icon={<Siren className="size-3.5 text-severity-high" />}
            label="Alerts fired"
            value={status.alertsFired.toLocaleString('en-IN')}
            valueClassName="text-severity-high"
            hint="score ≥ 70 → alert"
          />
        </Surface>
        <Surface pad="md">
          <Stat
            icon={<Zap className="size-3.5 text-ticker" />}
            label="Target rate"
            value={`${status.rate}/s`}
            hint="events per second"
          />
        </Surface>
        <Surface pad="md">
          <Stat
            icon={<Radio className="size-3.5 text-primary" />}
            label="Source mode"
            value={modeLabel(status.mode)}
            hint={running ? 'streaming' : 'stopped'}
          />
        </Surface>
      </div>

      {/* Live tape + ingestion-rate chart, both off the same singleton stream. */}
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LiveEventTape height={420} />
        </div>
        <div className="flex flex-col gap-3">
          <Surface pad="md" className="flex flex-col justify-center">
            <EventRateChart height={160} />
          </Surface>
          {/* Calm split-flap tape — a low-key ambient read of the same stream. */}
          <EventTicker
            items={ticker}
            live={running}
            title="Split-flap tape"
            max={TICKER_CAP}
            className="min-h-[13rem] flex-1"
          />
        </div>
      </div>
    </RouteTransition>
  )
}
