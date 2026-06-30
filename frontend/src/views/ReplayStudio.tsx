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
import { realtime, type RealtimeStatus } from '@/lib/realtime'
import { PageHeader } from '@/components/PageHeader'
import { LiveEventTape } from '@/components/realtime/LiveEventTape'
import { EventRateChart } from '@/components/charts/EventRateChart'
import { Surface } from '@/components/ui/surface'
import { Stat } from '@/components/ui/stat'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

const POLL_MS = 1500

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

  // Reflect a control action immediately rather than waiting up to POLL_MS for the next tick.
  const sync = () => setStatus(realtime.status())

  const running = status.running

  return (
    <div className="space-y-4">
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
        <Surface pad="md" className="flex flex-col justify-center">
          <EventRateChart height={160} />
        </Surface>
      </div>
    </div>
  )
}
