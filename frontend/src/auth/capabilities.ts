/**
 * RBAC capability matrix — the **Part 24.1 table encoded exactly** (8 roles × 9 capabilities), the
 * single source of truth for every route guard and conditionally-rendered control. The client guard
 * is **defense-in-depth**; the server (BACKEND/Keycloak) is authoritative (prompt §3, §7).
 *
 * Cell semantics mirror the blueprint's ✅ / ⚠️ / ❌:
 *   - allowed:false                         → ❌
 *   - allowed:true (no constraint)          → ✅
 *   - allowed:true + constraint             → ⚠️ "available but constrained/logged"
 *   - `scope` qualifies a ✅ (assigned / all / de-identified / read-only).
 *
 * SoD rule (Part 19.6): the model deployer cannot label/close their own alerts; the investigator
 * cannot tune the rules generating their own alerts. Encoded structurally (model_engineer has
 * disposition=❌, analyst/senior have tune_rules=❌) and enforced contextually via `violatesSoD`.
 */

export type Role =
  | 'analyst'
  | 'senior_investigator'
  | 'team_lead'
  | 'compliance_officer'
  | 'auditor'
  | 'model_engineer'
  | 'platform_admin'
  | 'service_account'

export type Capability =
  | 'view_alerts'
  | 'triage'
  | 'disposition'
  | 'request_block'
  | 'unmask_pii'
  | 'tune_rules'
  | 'train_models'
  | 'view_audit'
  | 'admin'

export const CAPABILITIES: Capability[] = [
  'view_alerts',
  'triage',
  'disposition',
  'request_block',
  'unmask_pii',
  'tune_rules',
  'train_models',
  'view_audit',
  'admin',
]

export const CAPABILITY_LABELS: Record<Capability, string> = {
  view_alerts: 'View alerts',
  triage: 'Triage / assign',
  disposition: 'Disposition (fraud/FP)',
  request_block: 'Request block',
  unmask_pii: 'Unmask PII',
  tune_rules: 'Tune rules/thresholds',
  train_models: 'Train/deploy models',
  view_audit: 'View audit log',
  admin: 'Admin (users/infra)',
}

export interface Cell {
  allowed: boolean
  /** Present when ⚠️ — the constraint shown in the UI (case-scoped, logged, de-identified, …). */
  constraint?: string
  /** Qualifies a ✅ view: 'assigned' | 'all' | 'de-identified' | 'read-only' | 'none' | 'own'. */
  scope?: string
}

const A = (scope?: string): Cell => ({ allowed: true, ...(scope ? { scope } : {}) }) // ✅
const W = (constraint: string, scope?: string): Cell => ({
  allowed: true,
  constraint,
  ...(scope ? { scope } : {}),
}) // ⚠️
const N: Cell = { allowed: false } // ❌

export const MATRIX: Record<Role, Record<Capability, Cell>> = {
  analyst: {
    view_alerts: A('assigned'),
    triage: A(),
    disposition: A(),
    request_block: W('request'),
    unmask_pii: W('case-scoped, logged'),
    tune_rules: N,
    train_models: N,
    view_audit: N,
    admin: N,
  },
  senior_investigator: {
    view_alerts: A('all'),
    triage: A(),
    disposition: A(),
    request_block: A(),
    unmask_pii: W('logged'),
    tune_rules: N,
    train_models: N,
    view_audit: W('view own', 'own'),
    admin: N,
  },
  team_lead: {
    view_alerts: A('all'),
    triage: A(),
    disposition: W('override'),
    request_block: W('approve'),
    unmask_pii: W('logged'),
    tune_rules: W('propose'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  compliance_officer: {
    view_alerts: A('all'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: W('logged'),
    tune_rules: W('change-controlled'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  auditor: {
    view_alerts: A('read-only'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: A('full'),
    admin: N,
  },
  model_engineer: {
    view_alerts: W('de-identified only', 'de-identified'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: W('with sign-off'),
    view_audit: W('view own', 'own'),
    admin: N,
  },
  platform_admin: {
    view_alerts: { allowed: false, scope: 'none' }, // ❌ no case data
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: W('deploy infra'),
    view_audit: A(),
    admin: A(),
  },
  service_account: {
    view_alerts: W('scoped tokens'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: W('write-only'),
    admin: N,
  },
}

/* ── helpers ────────────────────────────────────────────────────────────── */

export function cell(role: Role, capability: Capability): Cell {
  return MATRIX[role][capability]
}

/** True if the role may use the capability at all (✅ or ⚠️). */
export function can(role: Role | undefined, capability: Capability): boolean {
  if (!role) return false
  return MATRIX[role][capability].allowed
}

/** The ⚠️ constraint string, or undefined for ✅/❌. */
export function constraintFor(role: Role | undefined, capability: Capability): string | undefined {
  if (!role) return undefined
  return MATRIX[role][capability].constraint
}

/** Roles that may view case data (PII-bearing alert/entity detail): excludes de-identified-only and no-case-data. */
export function canViewCaseData(role: Role | undefined): boolean {
  if (!role) return false
  const c = MATRIX[role].view_alerts
  return (
    c.allowed && c.scope !== 'de-identified' && c.scope !== 'none' && role !== 'service_account'
  )
}

/**
 * Contextual SoD (Part 19.6). Returns a reason string if the action is forbidden by separation of
 * duties given the actor/owner, else null. Used to hide controls beyond the static matrix:
 *  - a model deployer cannot label/close an alert (even one they didn't generate);
 *  - the investigator who generated an alert cannot tune the rule that produced it.
 */
export function violatesSoD(
  role: Role,
  capability: Capability,
  ctx?: { isOwnAlert?: boolean; isOwnRule?: boolean },
): string | null {
  if (role === 'model_engineer' && (capability === 'disposition' || capability === 'triage')) {
    return 'Separation of duties: a model deployer cannot label or close alerts (Part 19.6).'
  }
  if (
    capability === 'tune_rules' &&
    ctx?.isOwnRule &&
    (role === 'analyst' || role === 'senior_investigator')
  ) {
    return 'Separation of duties: an investigator cannot tune the rule that generated their own alert (Part 19.6).'
  }
  return null
}

/* ── role metadata (labels, default landing, persona summary) ───────────── */

export interface RoleMeta {
  label: string
  short: string
  defaultRoute: string
  description: string
}

export const ROLE_META: Record<Role, RoleMeta> = {
  analyst: {
    label: 'Analyst (L1 investigator)',
    short: 'Analyst',
    defaultRoute: '/triage',
    description: 'Triages assigned alerts, investigates, and dispositions. Case-scoped unmask.',
  },
  senior_investigator: {
    label: 'Senior Investigator',
    short: 'Senior',
    defaultRoute: '/triage',
    description: 'Sees all alerts, dispositions, requests blocks, and unmasks (logged).',
  },
  team_lead: {
    label: 'Team Lead / MLRO',
    short: 'Team Lead',
    defaultRoute: '/triage',
    description: 'Overrides dispositions, approves blocks, proposes rules, sees the audit log.',
  },
  compliance_officer: {
    label: 'Compliance Officer',
    short: 'Compliance',
    defaultRoute: '/compliance',
    description: 'Change-controls rules/thresholds, EWS/RFA coverage, CRILC/FMR exports.',
  },
  auditor: {
    label: 'Auditor',
    short: 'Auditor',
    defaultRoute: '/audit',
    description: 'Read-only immutable audit trail, including who-viewed-whom and who-closed-what.',
  },
  model_engineer: {
    label: 'Model Engineer / Data Scientist',
    short: 'Model Eng',
    defaultRoute: '/models',
    description: 'Registry champion/challenger, drift, model quality — de-identified data only.',
  },
  platform_admin: {
    label: 'Platform Admin',
    short: 'Admin',
    defaultRoute: '/admin',
    description: 'Users/roles, rule deployment, system health (Grafana). No case data.',
  },
  service_account: {
    label: 'Service Account',
    short: 'Service',
    defaultRoute: '/',
    description: 'Scoped tokens; audit write-only. Not an interactive console user.',
  },
}

/** Roles a human can sign in as (excludes service accounts) — for the demo role picker. */
export const HUMAN_ROLES: Role[] = [
  'analyst',
  'senior_investigator',
  'team_lead',
  'compliance_officer',
  'auditor',
  'model_engineer',
  'platform_admin',
]
