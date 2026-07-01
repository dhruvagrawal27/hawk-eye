/**
 * Realtime seam (study Phase 1 — ported from the prototype's lib/ws.ts).
 *
 * One singleton source, fanned out to every consumer via a Set<Listener>, so N widgets share ONE
 * stream with no per-widget reconnect. Two interchangeable implementations behind one interface:
 *
 *   MockReplaySource  — a self-contained generator (our backend has no WS/SSE yet). Front-loads a
 *                       high-risk "mule burst" so alerts fire within seconds, then steady traffic.
 *   WsRealtimeSource  — a singleton WebSocket with exponential-backoff reconnect (the real swap).
 *
 * Swapping mock → real is the single line at the bottom (`realtime = env.useMocks ? mock : ws`).
 * High-frequency tick state stays LOCAL to each consumer (never a global store) — see LiveEventTape.
 */
import { env } from '@/lib/env'
import type { RiskLevel } from '@/lib/risk'
import { riskLevelFromScore } from '@/lib/risk'
import type { Alert, Severity } from '@/lib/types'

export interface RealtimeTick {
  type: 'event.scored'
  tick_id: number
  employee_id: string
  account_id: string
  score: number // 0–100
  risk_level: RiskLevel
  is_alert: boolean
  top_signal: string | null
  amount: number // INR
  txn_type: 'credit' | 'debit' | 'access' | 'config'
  channel: string
  is_after_hours: boolean
  ts: string // ISO
  receivedAt: number // client receipt stamp (Date.now())
}

export interface AlertNewMessage {
  type: 'alert.new'
  alert: Alert
}
export interface AlertUpdatedMessage {
  type: 'alert.updated'
  alert: Pick<Alert, 'alert_id'> & Partial<Alert>
}

export type RealtimeMessage = RealtimeTick | AlertNewMessage | AlertUpdatedMessage
export type Listener = (m: RealtimeMessage) => void

export interface RealtimeStatus {
  running: boolean
  eventsPublished: number
  alertsFired: number
  rate: number // target events/sec
  mode: string
}

export interface RealtimeSource {
  connect(): void
  disconnect(): void
  subscribe(cb: Listener): () => void
  start(mode?: string, rate?: number): void
  stop(): void
  injectBurst(): void
  status(): RealtimeStatus
}

/* ── synthetic data for the mock generator ─────────────────────────────── */

const SIGNALS = [
  'OFF_HOURS_ACTIVITY',
  'JUST_UNDER_THRESHOLD',
  'NEW_BENEFICIARY_HIGH_VALUE',
  'PRIVILEGED_SESSION_CORRELATION',
  'MAKER_CHECKER_PAIR_FREQUENCY',
  'DORMANT_ACCOUNT_REACTIVATION',
  'BULK_EXPORT',
  'ENTITLEMENT_GRANT',
]
const CHANNELS = ['cbs', 'swift', 'internet', 'db', 'admin_console']
const TXN: RealtimeTick['txn_type'][] = ['credit', 'debit', 'access', 'config']

let _seq = 1000 // global monotonic source for tick_id / employee suffixes
const rnd = (n: number) => Math.floor(Math.random() * n)
const pick = <T>(a: readonly T[]): T => a[rnd(a.length)]
const empId = () => `EMP-${(7000 + rnd(900)).toString(16)}`
const acctId = () => `ACCT-${(1000 + rnd(9000)).toString(36)}`

function severityFromScore(score: number): Severity {
  if (score >= 85) return 'critical'
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

/** One synthetic scored event. `hot` front-loads the high-risk "mule burst". */
function makeTick(hot: boolean): RealtimeTick {
  const score = hot ? 70 + rnd(30) : Math.min(99, Math.max(2, Math.round(28 + (Math.random() ** 2) * 60)))
  const level: RiskLevel = riskLevelFromScore(score)
  const isAlert = score >= 70
  return {
    type: 'event.scored',
    tick_id: ++_seq,
    employee_id: empId(),
    account_id: acctId(),
    score,
    risk_level: level,
    is_alert: isAlert,
    top_signal: score >= 40 ? pick(SIGNALS) : null,
    amount: (1 + rnd(50)) * 100000 + rnd(99999),
    txn_type: pick(TXN),
    channel: pick(CHANNELS),
    is_after_hours: Math.random() < (hot ? 0.7 : 0.2),
    ts: new Date().toISOString(),
    receivedAt: Date.now(),
  }
}

function tickToAlert(t: RealtimeTick): Alert {
  return {
    alert_id: `alr_${t.tick_id.toString(36)}`,
    entity_id: t.employee_id,
    risk_score: t.score,
    severity: severityFromScore(t.score),
    confidence: 0.6 + Math.random() * 0.35,
    status: 'open',
    created_ts: t.ts,
    contributing_layers: t.score >= 85 ? ['L1_rules', 'L3_gbdt', 'L5_graph'] : ['L1_rules', 'L2_unsupervised'],
    reason_codes: [],
    exposure_inr: t.amount,
    sla_due_ts: new Date(Date.now() + 6 * 3600_000).toISOString(),
    pii_tokenized: true,
    alert_type: t.top_signal ?? 'suspicious_activity',
    title: t.top_signal ? t.top_signal.replace(/_/g, ' ').toLowerCase() : 'Suspicious activity',
  }
}

/* ── mock generator (default; no backend WS yet) ───────────────────────── */

class MockReplaySource implements RealtimeSource {
  private listeners = new Set<Listener>()
  private timer: ReturnType<typeof setInterval> | null = null
  private rate: number
  private mode = 'idle'
  private events = 0
  private alerts = 0
  private burst = 0 // remaining front-loaded hot events
  private lastByEmp = new Map<string, number>() // throttle non-alert chatter per employee

  constructor(rate = 50) {
    this.rate = rate
  }

  private emit(m: RealtimeMessage) {
    for (const l of this.listeners) l(m)
  }

  private fire = () => {
    const hot = this.burst > 0
    if (hot) this.burst--
    const t = makeTick(hot)
    // At low rates, throttle low-risk chatter to ~1/sec per employee (mirrors backend _emit_tick).
    // At high rates (>=20/s) we want the full firehose, so the tape reads the real ~50 eps.
    if (!t.is_alert && this.rate < 20) {
      const last = this.lastByEmp.get(t.employee_id) ?? 0
      if (t.receivedAt - last < 1000) return
      this.lastByEmp.set(t.employee_id, t.receivedAt)
    }
    this.events++
    this.emit(t)
    if (t.is_alert) {
      this.alerts++
      this.emit({ type: 'alert.new', alert: tickToAlert(t) })
    }
  }

  connect() {
    this.start('steady')
  }
  disconnect() {
    this.stop()
  }

  start(mode = 'steady', rate?: number) {
    if (rate) this.rate = rate
    this.mode = mode
    if (mode === 'mule_burst' || this.events === 0) this.burst = 12 // front-load hot events
    if (this.timer) return
    this.timer = setInterval(this.fire, Math.max(20, Math.round(1000 / this.rate)))
  }
  stop() {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    this.mode = 'idle'
  }
  injectBurst() {
    this.burst += 8
    if (!this.timer) this.start('mule_burst')
  }

  subscribe(cb: Listener) {
    this.listeners.add(cb)
    return () => {
      this.listeners.delete(cb)
    }
  }

  status(): RealtimeStatus {
    return {
      running: this.timer !== null,
      eventsPublished: this.events,
      alertsFired: this.alerts,
      rate: this.rate,
      mode: this.mode,
    }
  }
}

/* ── real WebSocket (the swap target; unused until the backend streams) ──── */

class WsRealtimeSource implements RealtimeSource {
  private listeners = new Set<Listener>()
  private socket: WebSocket | null = null
  private backoff = 1000
  private events = 0
  private alerts = 0
  private closed = false

  private emit(m: RealtimeMessage) {
    for (const l of this.listeners) l(m)
  }

  connect() {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) return
    this.closed = false
    const url = env.wsBaseUrl
    try {
      this.socket = new WebSocket(url)
    } catch {
      this.scheduleReconnect()
      return
    }
    this.socket.onopen = () => {
      this.backoff = 1000
    }
    this.socket.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data) as RealtimeMessage
        if (m.type === 'event.scored') this.events++
        else if (m.type === 'alert.new') this.alerts++
        this.emit(m)
      } catch {
        /* ignore malformed frames */
      }
    }
    this.socket.onclose = () => {
      if (!this.closed) this.scheduleReconnect()
    }
    this.socket.onerror = () => this.socket?.close()
  }

  private scheduleReconnect() {
    setTimeout(() => this.connect(), this.backoff)
    this.backoff = Math.min(15000, Math.round(this.backoff * 1.6))
  }

  disconnect() {
    this.closed = true
    this.socket?.close()
    this.socket = null
  }
  subscribe(cb: Listener) {
    this.listeners.add(cb)
    return () => {
      this.listeners.delete(cb)
    }
  }
  // No client-side control of a real producer; these are no-ops for parity.
  start() {}
  stop() {}
  injectBurst() {}
  status(): RealtimeStatus {
    return {
      running: this.socket?.readyState === WebSocket.OPEN,
      eventsPublished: this.events,
      alertsFired: this.alerts,
      rate: 0,
      mode: 'ws',
    }
  }
}

/**
 * THE SWAP (now live): mock generator in mock mode (no backend), real WebSocket to /ws/alerts
 * otherwise — the backend now streams event.scored / alert.new from the online pipeline.
 */
export const realtime: RealtimeSource = env.useMocks
  ? new MockReplaySource()
  : new WsRealtimeSource()
export const WS_AVAILABLE = true
