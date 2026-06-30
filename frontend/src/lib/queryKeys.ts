/** Stable TanStack Query keys — one place so cache invalidation after disposition/assign is precise. */
import type { AlertQuery, AuditQuery } from './types'

export const queryKeys = {
  alerts: (query: AlertQuery = {}) => ['alerts', query] as const,
  alert: (id: string) => ['alert', id] as const,
  entity: (id: string) => ['entity', id] as const,
  entityTimeline: (id: string) => ['entity', id, 'timeline'] as const,
  entityGraph: (id: string) => ['entity', id, 'graph'] as const,
  entityPeers: (id: string) => ['entity', id, 'peers'] as const,
  explanation: (alertId: string) => ['explanation', alertId] as const,
  narrative: (alertId: string) => ['narrative', alertId] as const,
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
} as const
