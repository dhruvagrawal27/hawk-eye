/**
 * EventTicker — a calm split-flap tape of the synthetic event stream (docs/ui/UI_UPLIFT.md §3).
 *
 * A low-key, terminal-style tape for the live (mock/replay) event feed: newest at the top, each row a
 * monospaced timestamp + actor + a short line, tinted by risk band. Deliberately understated — it's
 * ambient context, not the main event; it must stay **off** dense data screens. New rows enter via
 * AutoAnimate (disabled under reduced motion). Presentational: it renders what it's given.
 */
import { cn } from '@/lib/cn'
import { riskColor, type RiskLevel } from '@/lib/risk'
import { useAutoAnimateList } from './motion'

export interface TickerItem {
  id: string
  /** Preformatted timestamp (e.g. "12:04:31"). Evidence → monospace. */
  ts: string
  /** Short actor / entity token. */
  actor: string
  /** One-line description of the event. */
  text: string
  /** Optional risk band for the left tick + amount tint. */
  level?: RiskLevel
  /** Optional right-aligned figure (already formatted). */
  amount?: string
}

export interface EventTickerProps {
  items: TickerItem[]
  /** Show the pulsing "live" indicator in the header. */
  live?: boolean
  title?: string
  /** Cap rows rendered (newest kept). */
  max?: number
  className?: string
}

export function EventTicker({
  items,
  live = false,
  title = 'Event tape',
  max = 12,
  className,
}: EventTickerProps) {
  const [listRef] = useAutoAnimateList<HTMLUListElement>()
  const rows = items.slice(0, max)

  return (
    <div
      className={cn(
        'flex h-full flex-col overflow-hidden rounded-md border border-border bg-card',
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="text-2xs font-medium uppercase tracking-widest text-muted-foreground">
          {title}
        </span>
        {live ? (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-tee motion-safe:animate-pulse-soft" />
            <span className="text-3xs font-medium uppercase tracking-widest text-tee">live</span>
          </span>
        ) : null}
      </div>
      <ul ref={listRef} className="min-h-0 flex-1 divide-y divide-border/60 overflow-auto">
        {rows.map((it) => {
          const color = it.level ? riskColor(it.level) : undefined
          return (
            <li key={it.id} className="flex items-center gap-2 px-3 py-1 text-xs">
              <span
                className="h-3 w-0.5 shrink-0 rounded-full"
                style={{ backgroundColor: color ?? 'hsl(var(--border))' }}
                aria-hidden
              />
              <span className="shrink-0 font-mono text-2xs tabular-nums text-muted-foreground">
                {it.ts}
              </span>
              <span className="shrink-0 font-mono text-2xs text-foreground/80">{it.actor}</span>
              <span className="truncate text-muted-foreground">{it.text}</span>
              {it.amount ? (
                <span
                  className="ml-auto shrink-0 font-mono text-2xs tabular-nums"
                  style={{ color: color ?? 'hsl(var(--foreground))' }}
                >
                  {it.amount}
                </span>
              ) : null}
            </li>
          )
        })}
        {rows.length === 0 ? (
          <li className="px-3 py-4 text-center text-2xs text-muted-foreground">No events yet</li>
        ) : null}
      </ul>
    </div>
  )
}
