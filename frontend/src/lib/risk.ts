/**
 * Single source of truth for risk → colour, read by badges, numbers, dots, row accents,
 * Recharts series and the Cytoscape stylesheet (study S3 / useRiskColor). The whole UI
 * speaks one severity palette instead of the rich colours being trapped in tiny badges.
 *
 * Backend severity is low | medium | high (contract). `critical` is a UI-only intensification
 * for the most extreme scores so the terminal can shout the worst cases; `flat` = no signal.
 */

import type { CSSProperties } from 'react'

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | 'flat'

/** Visual band from a 0–100 risk score. */
export function riskLevelFromScore(score: number | null | undefined): RiskLevel {
  if (score == null || Number.isNaN(score)) return 'flat'
  if (score >= 85) return 'critical'
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

/** Band from either a numeric score or a severity string. */
export function riskLevel(input: number | string | null | undefined): RiskLevel {
  if (typeof input === 'number') return riskLevelFromScore(input)
  switch ((input ?? '').toString().toLowerCase()) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'high'
    case 'medium':
      return 'medium'
    case 'low':
      return 'low'
    default:
      return 'flat'
  }
}

/** The CSS custom-property expression for a level (for inline styles / charts / cytoscape). */
export const RISK_VAR: Record<RiskLevel, string> = {
  low: 'var(--severity-low)',
  medium: 'var(--severity-medium)',
  high: 'var(--severity-high)',
  critical: 'var(--severity-critical)',
  flat: 'var(--risk-flat)',
}

/** Tailwind text-colour class per level (uses the `risk` palette alias). */
export const RISK_TEXT: Record<RiskLevel, string> = {
  low: 'text-risk-low',
  medium: 'text-risk-medium',
  high: 'text-risk-high',
  critical: 'text-risk-critical',
  flat: 'text-risk-flat',
}

/** A resolved `hsl(...)` string for non-Tailwind consumers (Recharts, Cytoscape). */
export function riskColor(input: number | string | null | undefined): string {
  return `hsl(${RISK_VAR[riskLevel(input)]})`
}

/** Inline style for a left-accent bar / risk-tinted row background, keyed by level. */
export function riskRowStyle(input: number | string | null | undefined): CSSProperties {
  const level = riskLevel(input)
  return {
    boxShadow: `inset 3px 0 0 0 hsl(${RISK_VAR[level]})`,
    backgroundColor: level === 'flat' ? undefined : `hsl(${RISK_VAR[level]} / 0.05)`,
  }
}
