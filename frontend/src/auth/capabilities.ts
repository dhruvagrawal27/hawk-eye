/**
 * RBAC capability matrix — the **bank org-chart model encoded exactly** (12 roles × 9 capabilities),
 * the single source of truth for every route guard and conditionally-rendered control. FROZEN per
 * docs/BANK_ROLES.md; capability semantics and the 9 capabilities are unchanged from Part 24.1 —
 * only the role identities, hierarchy, and the two new oversight tiers (CGM/board) are new. The
 * client guard is **defense-in-depth**; the server (BACKEND/Keycloak) is authoritative (prompt §3, §7).
 *
 * Cell semantics mirror the blueprint's ✅ / ⚠️ / ❌:
 *   - allowed:false                         → ❌
 *   - allowed:true (no constraint)          → ✅
 *   - allowed:true + constraint             → ⚠️ "available but constrained/logged"
 *   - `scope` qualifies a ✅ (assigned / all / de-identified / read-only).
 *
 * SoD rule (Part 19.6, re-keyed): the model deployer cannot label/close their own alerts; an
 * investigator cannot tune the rules generating their own alerts. Encoded structurally
 * (data_science_lead has disposition=❌; relationship_manager/branch_manager/cluster_head have
 * tune_rules ❌/conditional) and enforced contextually via `violatesSoD`.
 */

export type Role =
  | 'relationship_manager'
  | 'branch_manager'
  | 'cluster_head'
  | 'agm_vigilance'
  | 'dgm_compliance'
  | 'data_science_lead'
  | 'cgm_risk'
  | 'chief_internal_auditor'
  | 'executive_director'
  | 'managing_director'
  | 'it_admin'
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

// Transcribed verbatim from docs/BANK_ROLES.md (columns: view, triage, disposition, request_block,
// unmask, tune, train, audit, admin). 12 rows × 9 capabilities — see assert_matrix_complete().
export const MATRIX: Record<Role, Record<Capability, Cell>> = {
  relationship_manager: {
    view_alerts: W('assigned_only', 'assigned'),
    triage: A(),
    disposition: A(),
    request_block: W('request_only'),
    unmask_pii: W('case_scoped_logged'),
    tune_rules: N,
    train_models: N,
    view_audit: N,
    admin: N,
  },
  branch_manager: {
    view_alerts: A('all'),
    triage: A(),
    disposition: A(),
    request_block: A(),
    unmask_pii: W('logged'),
    tune_rules: N,
    train_models: N,
    view_audit: W('view_own', 'own'),
    admin: N,
  },
  cluster_head: {
    view_alerts: A('all'),
    triage: A(),
    disposition: W('override'),
    request_block: W('approve'),
    unmask_pii: W('logged'),
    tune_rules: W('propose_only'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  agm_vigilance: {
    view_alerts: A('all'),
    triage: A(),
    disposition: W('override'),
    request_block: W('approve'),
    unmask_pii: W('logged'),
    tune_rules: W('change_controlled'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  dgm_compliance: {
    view_alerts: A('all'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: W('logged'),
    tune_rules: W('change_controlled'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  data_science_lead: {
    view_alerts: W('de_identified_only', 'de-identified'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: W('with_signoff'),
    view_audit: W('view_own', 'own'),
    admin: N,
  },
  cgm_risk: {
    view_alerts: W('de_identified_only', 'de-identified'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: W('change_controlled'),
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  chief_internal_auditor: {
    view_alerts: W('read_only', 'read-only'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  executive_director: {
    view_alerts: W('de_identified_only', 'de-identified'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  managing_director: {
    view_alerts: W('de_identified_only', 'de-identified'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: A(),
    admin: N,
  },
  it_admin: {
    view_alerts: { allowed: false, scope: 'none' }, // ❌ no case data
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: W('deploy_infra_only'),
    view_audit: A(),
    admin: A(),
  },
  service_account: {
    view_alerts: W('scoped_token'),
    triage: N,
    disposition: N,
    request_block: N,
    unmask_pii: N,
    tune_rules: N,
    train_models: N,
    view_audit: W('write_only'),
    admin: N,
  },
}

/**
 * Matrix completeness self-check — the bank model is exactly 12 roles × 9 capabilities. Mirrors the
 * backend's `assert_matrix_complete()`. Runs once at module load so a mis-sized matrix fails fast
 * rather than silently dropping a role or capability.
 */
export function assertMatrixComplete(): void {
  const roles = Object.keys(MATRIX) as Role[]
  if (roles.length !== 12) {
    throw new Error(`RBAC matrix must have 12 roles, found ${roles.length}`)
  }
  for (const role of roles) {
    const caps = Object.keys(MATRIX[role]) as Capability[]
    if (caps.length !== 9) {
      throw new Error(`RBAC matrix role ${role} must have 9 capabilities, found ${caps.length}`)
    }
  }
}

assertMatrixComplete()

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

/** All roles that hold a capability (✅ or ⚠️), excluding the non-human service account — used to
 *  tell a blocked user *who* owns an action their role can't perform. */
export function rolesWithCapability(capability: Capability): Role[] {
  return (Object.keys(MATRIX) as Role[]).filter(
    (r) => MATRIX[r][capability].allowed && r !== 'service_account',
  )
}

/**
 * Contextual SoD (Part 19.6, re-keyed for the bank model). Returns a reason string if the action is
 * forbidden by separation of duties given the actor/owner, else null. Used to hide controls beyond
 * the static matrix:
 *  - a model deployer (data_science_lead) cannot label/close an alert (even one they didn't generate);
 *  - an investigator who generated an alert cannot tune the rule that produced it
 *    (relationship_manager / branch_manager / cluster_head).
 */
export function violatesSoD(
  role: Role,
  capability: Capability,
  ctx?: { isOwnAlert?: boolean; isOwnRule?: boolean },
): string | null {
  if (role === 'data_science_lead' && (capability === 'disposition' || capability === 'triage')) {
    return 'Separation of duties: a model deployer cannot label or close alerts (Part 19.6).'
  }
  if (
    capability === 'tune_rules' &&
    ctx?.isOwnRule &&
    (role === 'relationship_manager' || role === 'branch_manager' || role === 'cluster_head')
  ) {
    return 'Separation of duties: an investigator cannot tune the rule that generated their own alert (Part 19.6).'
  }
  return null
}

/* ── role metadata (org-chart placement, default landing, persona summary) ─ */

export interface RoleMeta {
  label: string
  short: string
  /** Org-chart tier (Branch · Cluster/Zone · Dept (HO) · Executive · Board · Dept (IT) · System). */
  tier: string
  /** RBI Three Lines of Defense ('1st' · '2nd' · '3rd' · 'Exec'), or '—' for non-LoD roles. */
  line: string
  /** Department / function the role sits in. */
  dept: string
  /** Role this role reports to, or null at the top of the chart / for non-org roles. */
  reportsTo: Role | null
  defaultRoute: string
  description: string
}

// Mirrors the docs/BANK_ROLES.md metadata table exactly (tier / line / dept / reports_to /
// default_route). Record over ALL 12 roles for TypeScript exhaustiveness.
export const ROLE_META: Record<Role, RoleMeta> = {
  relationship_manager: {
    label: 'Relationship Manager',
    short: 'RM',
    tier: 'Branch',
    line: '1st',
    dept: 'Branch Ops',
    reportsTo: 'branch_manager',
    defaultRoute: '/triage',
    description:
      'Triages assigned alerts, investigates, and dispositions. Case-scoped, logged unmask.',
  },
  branch_manager: {
    label: 'Branch Manager',
    short: 'Branch Mgr',
    tier: 'Branch',
    line: '1st',
    dept: 'Branch Ops',
    reportsTo: 'cluster_head',
    defaultRoute: '/triage',
    description: 'Sees all branch alerts, dispositions, requests blocks, and unmasks (logged).',
  },
  cluster_head: {
    label: 'Cluster Head (Zonal Manager)',
    short: 'Cluster',
    tier: 'Cluster/Zone',
    line: '1st',
    dept: 'Zonal Office',
    reportsTo: 'agm_vigilance',
    defaultRoute: '/triage',
    description: 'Overrides dispositions, approves blocks, proposes rules, sees the audit log.',
  },
  agm_vigilance: {
    label: 'AGM — Vigilance & Fraud Risk',
    short: 'AGM Vig',
    tier: 'Dept (HO)',
    line: '1st',
    dept: 'Fraud Risk Mgmt (FRMD)',
    reportsTo: 'cgm_risk',
    defaultRoute: '/triage',
    description:
      'Fraud-function lead / MLRO: overrides, approves blocks, change-controls rules, full audit.',
  },
  dgm_compliance: {
    label: 'DGM — Risk & Compliance',
    short: 'DGM Comp',
    tier: 'Dept (HO)',
    line: '2nd',
    dept: 'Risk & Compliance',
    reportsTo: 'cgm_risk',
    defaultRoute: '/compliance',
    description: 'Change-controls rules/thresholds, EWS/RFA coverage, CRILC/FMR exports.',
  },
  data_science_lead: {
    label: 'Head — Data Science / Model Risk',
    short: 'Data Sci',
    tier: 'Dept (HO)',
    line: '2nd',
    dept: 'Analytics / Model Risk',
    reportsTo: 'cgm_risk',
    defaultRoute: '/models',
    description: 'Registry champion/challenger, drift, model quality — de-identified data only.',
  },
  cgm_risk: {
    label: 'CGM — Chief Risk Officer',
    short: 'CGM Risk',
    tier: 'Executive',
    line: '2nd',
    dept: 'Risk & Compliance',
    reportsTo: 'executive_director',
    defaultRoute: '/reporting',
    description: 'Chief Risk Officer: de-identified KRIs, change-controls rules, full audit.',
  },
  chief_internal_auditor: {
    label: 'Chief Internal Auditor',
    short: 'CIA',
    tier: 'Dept (HO)',
    line: '3rd',
    dept: 'Internal Audit',
    reportsTo: 'managing_director',
    defaultRoute: '/audit',
    description: 'Read-only immutable audit trail, including who-viewed-whom and who-closed-what.',
  },
  executive_director: {
    label: 'Executive Director',
    short: 'ED',
    tier: 'Board',
    line: 'Exec',
    dept: 'Board',
    reportsTo: 'managing_director',
    defaultRoute: '/reporting',
    description: 'Board oversight: de-identified aggregates and KRIs, full audit. No case PII.',
  },
  managing_director: {
    label: 'Managing Director & CEO',
    short: 'MD&CEO',
    tier: 'Board',
    line: 'Exec',
    dept: 'Board',
    reportsTo: null,
    defaultRoute: '/reporting',
    description: 'Top of chart: de-identified aggregates and KRIs, full audit. No case PII.',
  },
  it_admin: {
    label: 'IT / Platform Administrator',
    short: 'IT Admin',
    tier: 'Dept (IT)',
    line: '—',
    dept: 'Technology',
    reportsTo: null,
    defaultRoute: '/admin',
    description: 'Users/roles, infra deployment, system health (Grafana). No case data.',
  },
  service_account: {
    label: 'Service Account',
    short: 'Service',
    tier: 'System',
    line: '—',
    dept: 'System',
    reportsTo: null,
    defaultRoute: '/',
    description: 'Scoped tokens; audit write-only. Not an interactive console user.',
  },
}

/**
 * Roles a human can sign in as (excludes service accounts) — for the demo role picker.
 * Top-of-chart first, per docs/BANK_ROLES.md HUMAN_ROLES order.
 */
export const HUMAN_ROLES: Role[] = [
  'managing_director',
  'executive_director',
  'cgm_risk',
  'dgm_compliance',
  'agm_vigilance',
  'chief_internal_auditor',
  'data_science_lead',
  'cluster_head',
  'branch_manager',
  'relationship_manager',
  'it_admin',
]
