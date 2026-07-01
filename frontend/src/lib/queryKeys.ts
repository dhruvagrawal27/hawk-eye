/** Stable TanStack Query keys — one place so cache invalidation after disposition/assign is precise. */
import type { AlertQuery, AuditQuery } from './types'

export const queryKeys = {
  alerts: (query: AlertQuery = {}) => ['alerts', query] as const,
  alert: (id: string) => ['alert', id] as const,
  entity: (id: string) => ['entity', id] as const,
  entityTimeline: (id: string) => ['entity', id, 'timeline'] as const,
  entityGraph: (id: string, depth = 1) => ['entity', id, 'graph', depth] as const,
  entityPeers: (id: string) => ['entity', id, 'peers'] as const,
  scoreHistory: (id: string) => ['entity', id, 'score-history'] as const,
  graphOverview: (minScore = 0, limit?: number) =>
    ['graph', 'overview', minScore, limit ?? null] as const,
  explanation: (alertId: string) => ['explanation', alertId] as const,
  narrative: (alertId: string) => ['narrative', alertId] as const,
  attestation: (alertId: string) => ['narrative', alertId, 'attestation'] as const,
  rules: () => ['rules'] as const,
  models: () => ['models'] as const,
  drift: () => ['drift'] as const,
  modelMetrics: () => ['model-metrics'] as const,
  audit: (query: AuditQuery = {}) => ['audit', query] as const,
  users: () => ['admin', 'users'] as const,
  health: () => ['health'] as const,
  metrics: () => ['metrics'] as const,
  ewsCoverage: () => ['reports', 'ews-coverage'] as const,
  kris: () => ['reports', 'kris'] as const,
  fmr: () => ['reports', 'fmr'] as const,
  crilc: () => ['reports', 'crilc'] as const,
  cases: () => ['cases'] as const,
  case: (id: string) => ['case', id] as const,
  subThreshold: (limit = 20) => ['activity', 'sub-threshold', limit] as const,
} as const
