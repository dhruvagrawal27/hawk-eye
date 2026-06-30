/**
 * Realtime consumption hooks (study Phase 1). Thin wrappers over the singleton `realtime` source.
 * High-frequency state stays LOCAL to each consumer — never a global store — so a tick re-renders
 * only the widget that cares, not the tree.
 */
import { useEffect, useRef, useState } from 'react'
import { realtime, type RealtimeMessage } from '@/lib/realtime'

/** Subscribe a stable callback to the stream for the component's lifetime (connect is idempotent). */
export function useRealtimeSubscription(onMessage: (m: RealtimeMessage) => void): void {
  const ref = useRef(onMessage)
  ref.current = onMessage
  useEffect(() => {
    realtime.connect()
    const unsub = realtime.subscribe((m) => ref.current(m))
    return unsub
  }, [])
}

export interface RateBucket {
  t: number // 1s-floored unix ms
  events: number
  alerts: number
}

export interface EventRate {
  buckets: RateBucket[]
  eps: number // events/sec over the trailing window
  live: boolean // saw an event in the last ~5s
}

/**
 * Rolling events/sec over a fixed-width 1s-bucket window (study: ring buffer + ONE 1s interval that
 * rolls and zero-pads, never per-row timers). Powers both the EPS sparkline and the status-bar EPS.
 */
export function useEventRate(windowSec = 60): EventRate {
  const [buckets, setBuckets] = useState<RateBucket[]>(() => seedBuckets(windowSec))
  const pending = useRef({ events: 0, alerts: 0, last: 0 })

  useRealtimeSubscription((m) => {
    if (m.type === 'event.scored') {
      pending.current.events++
      pending.current.last = Date.now()
    } else if (m.type === 'alert.new') {
      pending.current.alerts++
    }
  })

  useEffect(() => {
    const id = setInterval(() => {
      const now = Math.floor(Date.now() / 1000) * 1000
      setBuckets((prev) => {
        const next = [...prev, { t: now, events: pending.current.events, alerts: pending.current.alerts }]
        pending.current.events = 0
        pending.current.alerts = 0
        return next.slice(-windowSec)
      })
    }, 1000)
    return () => clearInterval(id)
  }, [windowSec])

  const total = buckets.reduce((s, b) => s + b.events, 0)
  const eps = total / Math.max(1, buckets.length)
  const live = Date.now() - pending.current.last < 5000
  return { buckets, eps, live }
}

function seedBuckets(windowSec: number): RateBucket[] {
  const now = Math.floor(Date.now() / 1000) * 1000
  return Array.from({ length: windowSec }, (_, i) => ({
    t: now - (windowSec - 1 - i) * 1000,
    events: 0,
    alerts: 0,
  }))
}
