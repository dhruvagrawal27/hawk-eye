/**
 * Display + domain helpers. Conventions (CONTEXT.md §6):
 *  - Time is stored UTC ISO-8601 and **displayed in IST** (Asia/Kolkata).
 *  - Money is INR (Indian digit grouping, ₹48,00,000 / lakh-crore compact).
 *  - IDs carry prefixes: evt_ / alr_ / EMP- / RNG- / aud_ / ACCT- / BEN-.
 *  - Triage ranking is fused risk × monetary exposure × confidence (Part 11, l.387).
 */
import type { Alert, ContributingLayer, Severity, AlertStatus, ReasonCodeSource } from './types'

const IST = 'Asia/Kolkata'

/* ───────────────────────────── Time (UTC → IST) ─────────────────────────── */

const istDateTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
})
const istDate = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})
const istTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: true,
})

function toDate(iso: string | number | Date): Date {
  return iso instanceof Date ? iso : new Date(iso)
}

/** Full IST date-time, e.g. "30 Jun 2026, 08:11 AM". */
export function formatIST(iso: string | number | Date): string {
  const d = toDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return `${istDateTime.format(d)} IST`
}
export function formatISTDate(iso: string | number | Date): string {
  const d = toDate(iso)
  return Number.isNaN(d.getTime()) ? '—' : istDate.format(d)
}
export function formatISTTime(iso: string | number | Date): string {
  const d = toDate(iso)
  return Number.isNaN(d.getTime()) ? '—' : istTime.format(d)
}

/** Compact relative time, e.g. "in 29d", "3h ago", "just now". `now` is injectable for tests. */
export function formatRelative(iso: string | number | Date, now: Date = new Date()): string {
  const d = toDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const ms = d.getTime() - now.getTime()
  const past = ms < 0
  const abs = Math.abs(ms)
  const units: [number, string][] = [
    [86_400_000, 'd'],
    [3_600_000, 'h'],
    [60_000, 'm'],
    [1_000, 's'],
  ]
  if (abs < 30_000) return 'just now'
  for (const [unitMs, label] of units) {
    if (abs >= unitMs) {
      const v = Math.round(abs / unitMs)
      return past ? `${v}${label} ago` : `in ${v}${label}`
    }
  }
  return 'just now'
}

/* ───────────────────────────── Money (INR) ──────────────────────────────── */

const inr = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

/** ₹48,00,000 (full Indian grouping). */
export function formatINR(rupees: number | null | undefined): string {
  if (rupees == null || Number.isNaN(rupees)) return '—'
  return inr.format(rupees)
}

/** Compact lakh/crore, e.g. "₹48.0 L", "₹1.20 Cr" — for dense tables and KRI cards. */
export function formatINRCompact(rupees: number | null | undefined): string {
  if (rupees == null || Number.isNaN(rupees)) return '—'
  const abs = Math.abs(rupees)
  const sign = rupees < 0 ? '-' : ''
  if (abs >= 1_00_00_000) return `${sign}₹${(abs / 1_00_00_000).toFixed(2)} Cr`
  if (abs >= 1_00_000) return `${sign}₹${(abs / 1_00_000).toFixed(1)} L`
  if (abs >= 1_000) return `${sign}₹${(abs / 1_000).toFixed(1)}k`
  return `${sign}₹${abs}`
}

/* ───────────────────────────── Numbers ──────────────────────────────────── */

export function formatPercent(value: number, digits = 0): string {
  if (Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}
export function formatNumber(value: number, digits = 0): string {
  if (Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value)
}
/** Signed, fixed-precision (for SHAP contributions: +0.31 / -0.12). */
export function formatSigned(value: number, digits = 2): string {
  const s = value.toFixed(digits)
  return value > 0 ? `+${s}` : s
}

/* ───────────────────────────── IDs ──────────────────────────────────────── */

export const idPattern = {
  event: /^evt_/i,
  alert: /^alr_/i,
  entity: /^EMP-/i,
  ring: /^RNG-/i,
  audit: /^aud_/i,
  account: /^ACCT-/i,
  beneficiary: /^BEN-/i,
} as const

export function isEventId(v: string): boolean {
  return idPattern.event.test(v)
}
export function isAlertId(v: string): boolean {
  return idPattern.alert.test(v)
}
export function isEntityId(v: string): boolean {
  return idPattern.entity.test(v)
}
export function isRingId(v: string): boolean {
  return idPattern.ring.test(v)
}
export function isAuditId(v: string): boolean {
  return idPattern.audit.test(v)
}
/** A tokenized PII value is anything prefixed EMP-/ACCT-/BEN- (CONTEXT.md §6 / Part 25.3). */
export function isTokenizedPii(v: string): boolean {
  return idPattern.entity.test(v) || idPattern.account.test(v) || idPattern.beneficiary.test(v)
}

/* ───────────────────────────── Humanize ─────────────────────────────────── */

/** snake_case verb/feature → "Title Case" label, e.g. create_beneficiary → "Create Beneficiary". */
export function humanize(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim()
}

/**
 * Plain-English names for the technical model/rule signal tokens, so investigators and stakeholders
 * read "Fast payment to a new payee" instead of "New Beneficiary To Payment Latency Min". Unknown
 * tokens fall back to humanize() so new signals still render legibly.
 */
export const featureFriendlyNames: Record<string, string> = {
  off_hours_activity_rate_30d: 'Off-hours activity (vs usual)',
  off_hours_activity_rate: 'Off-hours activity (vs usual)',
  off_hours_flag: 'Outside business hours',
  privileged_session_off_hours: 'Privileged session, off-hours',
  maker_checker_pair_frequency_30d: 'Recurring maker–checker pair',
  new_beneficiary_to_payment_latency_min: 'Fast payment to a new payee',
  db_rows_read_zscore_vs_peer: 'Reading unusually many records vs peers',
  rows_read_zscore_vs_peer: 'Reading unusually many records vs peers',
  export_volume_vs_baseline: 'Bulk data export vs baseline',
  amount_zscore_vs_peer: 'Transaction amount vs peers',
  amount_zscore: 'Transaction amount vs peers',
  failed_login_burst: 'Burst of failed logins',
  role_change_recency: 'Recently changed role',
  reversal_clustering_7d: 'Clustered transaction reversals',
  swift_message_without_cbs_recon: 'SWIFT message with no core-banking match',
  swift_without_cbs: 'SWIFT message with no core-banking match',
  entitlement_change_velocity: 'Rapid access-entitlement changes',
  dormant_account_reactivation: 'Dormant account reactivated',
  standing_privilege_unused: 'Standing privilege never used',
  vendor_bank_detail_overlap: "Vendor shares an employee's bank details",
  geo_velocity_impossible: 'Impossible travel between logins',
  beneficiary_age_days: 'Age of the payee account',
  actor_tenure_days: 'Employee tenure',
  booking_latency_min: 'Trade booked-to-settled delay',
  borrower_file_completeness: 'Loan file completeness',
  days_since_last_activity: 'Days since last activity',
  velocity_1h: 'Actions in the last hour',
  new_beneficiary: 'New payee just created',
  db_write_no_app_txn: 'Direct DB write, no app transaction',
}

export function featureFriendlyLabel(name: string | null | undefined): string {
  if (!name) return '—'
  return featureFriendlyNames[name.toLowerCase()] ?? humanize(name)
}

export const layerLabels: Record<string, string> = {
  L1_rules: 'L1 · Rules',
  L2_unsupervised: 'L2 · Anomaly',
  L3_gbdt: 'L3 · GBDT',
  L4_sequence: 'L4 · Sequence',
  L5_graph: 'L5 · Graph',
  L6_fusion: 'L6 · Fusion',
}
export function layerLabel(layer: ContributingLayer | string): string {
  return layerLabels[layer] ?? humanize(layer)
}

export const statusLabels: Record<AlertStatus, string> = {
  open: 'Open',
  assigned: 'Assigned',
  in_progress: 'In progress',
  escalated: 'Escalated',
  confirmed_fraud: 'Confirmed fraud',
  false_positive: 'False positive',
  inconclusive: 'Inconclusive',
  closed: 'Closed',
}
export function statusLabel(status: AlertStatus | string): string {
  return statusLabels[status as AlertStatus] ?? humanize(String(status))
}

export const reasonSourceLabels: Record<ReasonCodeSource, string> = {
  rule: 'Rule',
  shap: 'SHAP',
  graph: 'Graph',
}

/* ───────────────────────────── Severity / risk bands ────────────────────── */

export const severityRank: Record<Severity, number> = { critical: 4, high: 3, medium: 2, low: 1 }

/** Map a 0–100 risk score to a severity band (mirrors typical fusion cut-points). */
export function severityForScore(score: number): Severity {
  if (score >= 85) return 'critical'
  if (score >= 65) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

/* ───────────────────────────── Triage composite priority (Part 11) ──────── */

/**
 * Fused **risk × monetary exposure × confidence** ordering (blueprint Part 11, l.387; Part 24.4
 * screen 2). Exposure is log-compressed so a ₹48L alert doesn't drown a ₹5L critical, while still
 * letting money break ties — the queue honours server ordering first and falls back to this.
 * Returns a positive composite; higher = triage sooner.
 */
export function compositePriority(
  alert: Pick<Alert, 'risk_score' | 'exposure_inr' | 'confidence'>,
): number {
  const risk = clamp(alert.risk_score, 0, 100) / 100
  const confidence = clamp(alert.confidence, 0, 1)
  const exposure = Math.log10(1 + Math.max(0, alert.exposure_inr))
  return Number((risk * confidence * (1 + exposure) * 100).toFixed(2))
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

/* ───────────────────────────── SLA / TAT timer (Part 24.4 screen 2) ─────── */

export type SlaState = 'ok' | 'warn' | 'urgent' | 'breached'
export interface SlaInfo {
  state: SlaState
  msRemaining: number
  breached: boolean
  /** Compact label, e.g. "29d left", "4h left", "Breached 2d". */
  label: string
}

const SLA_URGENT_MS = 72 * 3_600_000 // < 3 days
const SLA_WARN_MS = 7 * 86_400_000 // < 7 days

/** Compute SLA/TAT state from `sla_due_ts` (RBI ≤30-day window). `now` injectable for tests. */
export function slaInfo(slaDueTs: string | number | Date, now: Date = new Date()): SlaInfo {
  const due = toDate(slaDueTs)
  if (Number.isNaN(due.getTime())) {
    return { state: 'ok', msRemaining: Number.POSITIVE_INFINITY, breached: false, label: '—' }
  }
  const msRemaining = due.getTime() - now.getTime()
  if (msRemaining < 0) {
    return {
      state: 'breached',
      msRemaining,
      breached: true,
      label: `Breached ${formatRelative(due, now).replace(' ago', '')}`,
    }
  }
  let state: SlaState = 'ok'
  if (msRemaining < SLA_URGENT_MS) state = 'urgent'
  else if (msRemaining < SLA_WARN_MS) state = 'warn'
  return {
    state,
    msRemaining,
    breached: false,
    label: `${formatRelative(due, now).replace('in ', '')} left`,
  }
}
