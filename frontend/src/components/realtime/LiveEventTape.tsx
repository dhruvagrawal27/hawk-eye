import * as React from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Activity, ArrowDownRight, ArrowUpRight, Moon, Pause, Play } from 'lucide-react'
import { useRealtimeSubscription } from '@/hooks/useRealtime'
import type { RealtimeTick } from '@/lib/realtime'
import { riskColor, RISK_TEXT, riskLevel } from '@/lib/risk'
import { formatINRCompact, formatISTTime } from '@/lib/format'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/cn'

/**
 * LiveEventTape — a Bloomberg-style live activity tape (study Phase 1 / §S1).
 *
 * ONE subscription for the widget's lifetime via {@link useRealtimeSubscription}; ticks land in a
 * hard-capped, newest-first ring buffer (`[tick, ...prev].slice(0, CAP)`) kept LOCAL to this widget
 * so a tick re-renders only the tape, never the tree. Pause is read from a ref inside the callback
 * (NOT effect deps) so toggling it never tears down the stream. Freshness is a pure CSS keyframe
 * (`animate-row-flash`) on a row KEYED by `tick_id` — a fresh mount replays the flash once, with no
 * per-row timers. The list is virtualized with @tanstack/react-virtual.
 */

const CAP = 120
const ROW_H = 30 // px — fixed row height for the virtualizer estimate

export interface LiveEventTapeProps {
  /** Scroll-viewport height in px (default 420). */
  height?: number
}

/** Mask a tokenized employee id for the tape: keep the prefix + last 2, dot out the middle. */
function maskEmployee(id: string): string {
  const dash = id.indexOf('-')
  if (dash < 0 || dash >= id.length - 1) return id
  const prefix = id.slice(0, dash + 1)
  const body = id.slice(dash + 1)
  if (body.length <= 2) return `${prefix}${body}`
  return `${prefix}••${body.slice(-2)}`
}

const DEBIT_LIKE = new Set<RealtimeTick['txn_type']>(['debit'])

export function LiveEventTape({ height = 420 }: LiveEventTapeProps): React.JSX.Element {
  const [rows, setRows] = React.useState<RealtimeTick[]>([])
  const [paused, setPaused] = React.useState(false)
  const [total, setTotal] = React.useState(0)

  // Pause is read from a ref INSIDE the callback so toggling it never re-subscribes.
  const pausedRef = React.useRef(paused)
  pausedRef.current = paused

  useRealtimeSubscription((m) => {
    if (m.type !== 'event.scored') return
    setTotal((n) => n + 1) // total counts the stream even while the tape is frozen
    if (pausedRef.current) return
    setRows((prev) => [m, ...prev].slice(0, CAP))
  })

  const scrollRef = React.useRef<HTMLDivElement>(null)
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 8,
    getItemKey: (i) => rows[i].tick_id, // stable, monotonic — drives the flash replay
  })

  const items = virtualizer.getVirtualItems()

  return (
    <Surface tone="operational" pad="none" className="flex flex-col overflow-hidden">
      <header className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="relative inline-flex size-2.5 items-center justify-center">
            <Activity className="size-3 text-ticker" aria-hidden />
            {!paused ? (
              <span className="absolute -right-1.5 -top-1 size-1.5 rounded-full bg-ticker motion-safe:animate-pulse-soft" />
            ) : null}
          </span>
          <Eyebrow>Live Event Tape</Eyebrow>
        </div>

        <div className="flex items-center gap-3">
          <span className="font-mono text-2xs tabular-nums text-muted-foreground">
            <span className="text-foreground">{rows.length}</span> rows{' '}
            <span className="text-muted-foreground/60">·</span>{' '}
            <span className="text-foreground">{total.toLocaleString('en-IN')}</span> total
          </span>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 gap-1 px-2 font-mono text-2xs uppercase tracking-wide"
            aria-pressed={paused}
            aria-label={paused ? 'Resume tape' : 'Pause tape'}
            onClick={() => setPaused((p) => !p)}
          >
            {paused ? <Play className="size-3" /> : <Pause className="size-3" />}
            {paused ? 'Play' : 'Pause'}
          </Button>
        </div>
      </header>

      {rows.length === 0 ? (
        <div
          className="flex items-center justify-center px-3 text-2xs text-muted-foreground"
          style={{ height }}
        >
          <span className="font-mono uppercase tracking-widest">Awaiting stream…</span>
        </div>
      ) : (
        <div ref={scrollRef} className="overflow-y-auto" style={{ height }}>
          <div className="relative w-full" style={{ height: virtualizer.getTotalSize() }}>
            {items.map((vi) => {
              const tick = rows[vi.index]
              return (
                <TapeRow
                  key={vi.key}
                  tick={tick}
                  top={vi.start}
                  measureRef={virtualizer.measureElement}
                  index={vi.index}
                />
              )
            })}
          </div>
        </div>
      )}
    </Surface>
  )
}

interface TapeRowProps {
  tick: RealtimeTick
  top: number
  index: number
  measureRef: (node: Element | null) => void
}

/**
 * A single tape row. Keyed by `tick_id` upstream, so each fresh row mounts with `animate-row-flash`
 * and the keyframe plays exactly once — no per-row setTimeout.
 */
const TapeRow = React.memo(function TapeRow({ tick, top, index, measureRef }: TapeRowProps) {
  const level = riskLevel(tick.score)
  const debit = DEBIT_LIKE.has(tick.txn_type)
  const DirIcon = debit ? ArrowDownRight : ArrowUpRight

  return (
    <div
      ref={measureRef}
      data-index={index}
      className="absolute inset-x-0 animate-row-flash"
      style={{ top, height: ROW_H }}
    >
      <div className="flex h-full items-center gap-2 border-b border-border/40 px-3 font-mono text-xs tabular-nums">
        {/* risk dot */}
        <span
          className="size-2 shrink-0 rounded-full"
          style={{ backgroundColor: riskColor(tick.score) }}
          aria-hidden
        />

        {/* score */}
        <span className={cn('w-7 shrink-0 text-right font-semibold', RISK_TEXT[level])}>
          {Math.round(tick.score)}
        </span>

        {/* masked employee */}
        <span className="w-20 shrink-0 truncate text-foreground/90" title={tick.employee_id}>
          {maskEmployee(tick.employee_id)}
        </span>

        {/* top signal chip */}
        <span className="min-w-0 flex-1">
          {tick.top_signal ? (
            <span
              className="inline-block max-w-full truncate rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 text-3xs uppercase tracking-wide text-muted-foreground"
              title={tick.top_signal}
            >
              {tick.top_signal.replace(/_/g, ' ')}
            </span>
          ) : (
            <span className="text-3xs text-muted-foreground/40">—</span>
          )}
        </span>

        {/* amount */}
        <span className="w-16 shrink-0 text-right text-foreground/90">
          {formatINRCompact(tick.amount)}
        </span>

        {/* txn direction */}
        <span
          className={cn(
            'flex w-4 shrink-0 items-center justify-center',
            debit ? 'text-risk-high' : 'text-risk-low',
          )}
          title={tick.txn_type}
          aria-label={tick.txn_type}
        >
          <DirIcon className="size-3.5" />
        </span>

        {/* after-hours */}
        <span className="flex w-4 shrink-0 items-center justify-center">
          {tick.is_after_hours ? (
            <Moon
              className="size-3 text-risk-medium"
              aria-label="After hours"
            />
          ) : null}
        </span>

        {/* time */}
        <span className="w-14 shrink-0 text-right text-2xs text-muted-foreground" title={tick.ts}>
          {formatISTTime(tick.ts)}
        </span>
      </div>
    </div>
  )
})
