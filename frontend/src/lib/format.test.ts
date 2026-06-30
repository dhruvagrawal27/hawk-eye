import { describe, expect, it } from 'vitest'
import {
  compositePriority,
  formatINR,
  formatINRCompact,
  formatIST,
  formatSigned,
  isAlertId,
  isEntityId,
  isEventId,
  isTokenizedPii,
  severityForScore,
  slaInfo,
} from './format'

describe('IST time display (CONTEXT.md §6)', () => {
  it('renders UTC as IST (+5:30) with an IST suffix', () => {
    // 2026-06-30T02:41:55Z → 08:11 IST on 30 Jun 2026
    const out = formatIST('2026-06-30T02:41:55Z')
    expect(out).toContain('30 Jun 2026')
    expect(out).toContain('08:11')
    expect(out).toContain('IST')
  })
  it('handles invalid input gracefully', () => {
    expect(formatIST('not-a-date')).toBe('—')
  })
})

describe('INR money (Part 24.5)', () => {
  it('groups in the Indian system', () => {
    expect(formatINR(4800000)).toBe('₹48,00,000')
  })
  it('compacts to lakh / crore', () => {
    expect(formatINRCompact(4800000)).toBe('₹48.0 L')
    expect(formatINRCompact(31000000)).toBe('₹3.10 Cr')
  })
  it('formats signed SHAP contributions', () => {
    expect(formatSigned(0.31)).toBe('+0.31')
    expect(formatSigned(-0.09)).toBe('-0.09')
  })
})

describe('composite triage priority (Part 11: risk × exposure × confidence)', () => {
  it('ranks the worked-burst alert above a lower risk/exposure alert', () => {
    const worked = compositePriority({ risk_score: 87, exposure_inr: 4800000, confidence: 0.82 })
    const minor = compositePriority({ risk_score: 45, exposure_inr: 180000, confidence: 0.4 })
    expect(worked).toBeGreaterThan(minor)
  })
  it('is monotonic in each factor', () => {
    const base = { risk_score: 60, exposure_inr: 1000000, confidence: 0.6 }
    expect(compositePriority({ ...base, risk_score: 80 })).toBeGreaterThan(compositePriority(base))
    expect(compositePriority({ ...base, exposure_inr: 10000000 })).toBeGreaterThan(
      compositePriority(base),
    )
    expect(compositePriority({ ...base, confidence: 0.9 })).toBeGreaterThan(compositePriority(base))
  })
})

describe('SLA/TAT state (Part 24.4 screen 2)', () => {
  const now = new Date('2026-06-30T00:00:00Z')
  it('is ok ~30 days out', () => {
    expect(slaInfo('2026-07-30T00:00:00Z', now).state).toBe('ok')
  })
  it('warns within 7 days', () => {
    expect(slaInfo('2026-07-05T00:00:00Z', now).state).toBe('warn')
  })
  it('is urgent within 72h', () => {
    expect(slaInfo('2026-07-01T00:00:00Z', now).state).toBe('urgent')
  })
  it('is breached past due', () => {
    const info = slaInfo('2026-06-28T00:00:00Z', now)
    expect(info.state).toBe('breached')
    expect(info.breached).toBe(true)
  })
})

describe('ID prefixes (CONTEXT.md §6)', () => {
  it('recognises each prefix', () => {
    expect(isEventId('evt_8f2a1c90')).toBe(true)
    expect(isAlertId('alr_3d7e22')).toBe(true)
    expect(isEntityId('EMP-7f3a')).toBe(true)
    expect(isTokenizedPii('ACCT-4d22')).toBe(true)
    expect(isTokenizedPii('BEN-9b1c')).toBe(true)
    expect(isTokenizedPii('peer_group')).toBe(false)
  })
})

describe('severity banding', () => {
  it('maps score to band', () => {
    expect(severityForScore(87)).toBe('critical')
    expect(severityForScore(70)).toBe('high')
    expect(severityForScore(50)).toBe('medium')
    expect(severityForScore(30)).toBe('low')
  })
})
