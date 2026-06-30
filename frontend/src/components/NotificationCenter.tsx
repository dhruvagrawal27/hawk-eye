/**
 * NotificationCenter (Agent C) — a Topbar bell that surfaces high/critical alerts off the realtime
 * seam. ONE subscription for the component's lifetime via {@link useRealtimeSubscription}; `alert.new`
 * messages for high/critical severity land in a hard-capped, newest-first ring buffer kept LOCAL to
 * this widget (never a global store), so a burst re-renders only the bell. An unread badge counts
 * notifications received while the panel is closed; opening or "mark all read" clears it. Clicking a
 * row deep-links to the alert. Money is INR, ids stay tokenized (golden rules #3/#5).
 */
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, CheckCheck } from 'lucide-react'
import { useRealtimeSubscription } from '@/hooks/useRealtime'
import type { RealtimeMessage } from '@/lib/realtime'
import type { Alert, Severity } from '@/lib/types'
import { riskColor, RISK_TEXT, riskLevel } from '@/lib/risk'
import { formatINRCompact, formatRelative, humanize } from '@/lib/format'
import { cn } from '@/lib/cn'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Eyebrow } from '@/components/ui/eyebrow'
import { ScrollArea } from '@/components/ui/scroll-area'

const CAP = 40 // ring-buffer size — newest CAP notifications, oldest dropped
const NOTIFY_SEVERITY = new Set<Severity>(['high', 'critical'])

interface Notification {
  id: string
  alert: Alert
  receivedAt: number
}

export function NotificationCenter() {
  const navigate = useNavigate()
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [open, setOpen] = useState(false)

  // Open state is read from a ref inside the callback so toggling it never re-subscribes; while the
  // panel is open we treat arrivals as already-seen (no unread bump).
  const openRef = useRef(open)
  openRef.current = open

  useRealtimeSubscription((m: RealtimeMessage) => {
    if (m.type !== 'alert.new') return
    if (!NOTIFY_SEVERITY.has(m.alert.severity)) return
    setItems((prev) =>
      [{ id: m.alert.alert_id, alert: m.alert, receivedAt: Date.now() }, ...prev].slice(0, CAP),
    )
    if (!openRef.current) setUnread((n) => Math.min(99, n + 1))
  })

  function onOpenChange(next: boolean) {
    setOpen(next)
    if (next) setUnread(0) // opening the panel acknowledges everything
  }

  function markAllRead() {
    setUnread(0)
  }

  function openAlert(alert: Alert) {
    setOpen(false)
    navigate(`/alerts/${alert.alert_id}`)
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="relative inline-flex size-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-ring"
          aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
        >
          <Bell className="size-4" />
          {unread > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 inline-flex min-w-4 items-center justify-center rounded-full bg-severity-critical px-1 text-[0.6rem] font-semibold leading-none text-white tabular-nums motion-safe:animate-pulse-soft">
              {unread > 99 ? '99+' : unread}
            </span>
          ) : null}
        </button>
      </PopoverTrigger>

      <PopoverContent align="end" className="w-80 p-0">
        <header className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <Eyebrow className="flex items-center gap-1.5">
            <Bell className="size-3" /> Alerts
          </Eyebrow>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-6 gap-1 px-2 text-2xs"
            onClick={markAllRead}
            disabled={unread === 0}
          >
            <CheckCheck className="size-3" /> Mark all read
          </Button>
        </header>

        {items.length === 0 ? (
          <div className="px-3 py-8 text-center text-xs text-muted-foreground">
            <Bell className="mx-auto mb-2 size-5 opacity-40" />
            <p className="font-mono uppercase tracking-widest">No high-risk alerts yet</p>
            <p className="mt-1 text-2xs">High and critical alerts will appear here in real time.</p>
          </div>
        ) : (
          <ScrollArea className="max-h-80">
            <ul className="divide-y divide-border/60">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => openAlert(n.alert)}
                    className="flex w-full items-start gap-2.5 px-3 py-2 text-left transition-colors hover:bg-muted/50 focus-ring"
                  >
                    <span
                      aria-hidden
                      className="mt-1 size-2 shrink-0 rounded-full"
                      style={{ backgroundColor: riskColor(n.alert.risk_score) }}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <span
                          className={cn(
                            'truncate text-xs font-medium',
                            RISK_TEXT[riskLevel(n.alert.risk_score)],
                          )}
                          title={n.alert.title ?? n.alert.alert_type}
                        >
                          {n.alert.title ?? humanize(n.alert.alert_type ?? 'Suspicious activity')}
                        </span>
                        <span className="shrink-0 text-2xs tabular-nums text-muted-foreground">
                          {formatRelative(n.receivedAt)}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-1.5 text-2xs text-muted-foreground">
                        <span className="font-mono">{n.alert.entity_id}</span>
                        <span className="opacity-50">·</span>
                        <span className="tabular-nums">
                          {formatINRCompact(n.alert.exposure_inr)}
                        </span>
                        <span className="opacity-50">·</span>
                        <span className="uppercase">{n.alert.severity}</span>
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </ScrollArea>
        )}
      </PopoverContent>
    </Popover>
  )
}
