import {
  LayoutDashboard,
  Inbox,
  FolderKanban,
  Scale,
  FileSearch,
  Boxes,
  BarChart3,
  Network,
  ServerCog,
  type LucideIcon,
} from 'lucide-react'
import type { Role } from '@/lib/types'

/**
 * Navigation + route-access map. The Sidebar filters items by the active role and the router gates
 * each screen with the same role set (RoleShell) — defense-in-depth over the bank org-chart matrix
 * (docs/BANK_ROLES.md). Role sets are derived from the screens in Part 24.4, re-keyed onto the
 * 12-role console model (11 human + 1 service).
 */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles: Role[]
  /** Blueprint screen number (Part 24.4) for traceability. */
  screen?: number
}

/** First-line investigation roles (triage / cases / case detail). */
const INVESTIGATORS: Role[] = [
  'relationship_manager',
  'branch_manager',
  'cluster_head',
  'agm_vigilance',
]

/** Every role that holds `view_audit` (the audit trail is the "watch-the-watchers" surface). */
const AUDIT_VIEWERS: Role[] = [
  'cluster_head',
  'agm_vigilance',
  'dgm_compliance',
  'cgm_risk',
  'chief_internal_auditor',
  'executive_director',
  'managing_director',
  'it_admin',
]

/** Management + board roles that read the reporting / KRI surface. */
const REPORTING_VIEWERS: Role[] = [
  'agm_vigilance',
  'dgm_compliance',
  'cgm_risk',
  'chief_internal_auditor',
  'executive_director',
  'managing_director',
  'it_admin',
]

/** Managers + executives who can read the org chart (reporting tree, Lines of Defense). */
const ORG_VIEWERS: Role[] = [
  'cluster_head',
  'agm_vigilance',
  'dgm_compliance',
  'cgm_risk',
  'executive_director',
  'managing_director',
  'chief_internal_auditor',
]

export const NAV_ITEMS: NavItem[] = [
  {
    to: '/',
    label: 'Dashboard',
    icon: LayoutDashboard,
    roles: [
      'relationship_manager',
      'branch_manager',
      'cluster_head',
      'agm_vigilance',
      'dgm_compliance',
      'data_science_lead',
      'cgm_risk',
      'chief_internal_auditor',
      'executive_director',
      'managing_director',
      'it_admin',
    ],
  },
  {
    to: '/triage',
    label: 'Triage queue',
    icon: Inbox,
    roles: INVESTIGATORS,
    screen: 2,
  },
  {
    to: '/cases',
    label: 'Cases',
    icon: FolderKanban,
    roles: INVESTIGATORS,
    screen: 4,
  },
  {
    to: '/compliance',
    label: 'Compliance',
    icon: Scale,
    roles: ['dgm_compliance', 'agm_vigilance'],
    screen: 5,
  },
  {
    to: '/audit',
    label: 'Auditor',
    icon: FileSearch,
    roles: AUDIT_VIEWERS,
    screen: 6,
  },
  {
    to: '/models',
    label: 'Model engineer',
    icon: Boxes,
    roles: ['data_science_lead', 'it_admin'],
    screen: 7,
  },
  {
    to: '/reporting',
    label: 'Reporting & KRIs',
    icon: BarChart3,
    roles: REPORTING_VIEWERS,
  },
  { to: '/org', label: 'Org chart', icon: Network, roles: ORG_VIEWERS },
  { to: '/admin', label: 'Admin', icon: ServerCog, roles: ['it_admin'], screen: 8 },
]

/** Role sets per gated route, reused by the router's RoleShell guards. */
export const ROUTE_ROLES = {
  triageAndCases: INVESTIGATORS,
  caseDetailViewers: [
    'relationship_manager',
    'branch_manager',
    'cluster_head',
    'agm_vigilance',
    'dgm_compliance',
  ] as Role[],
  compliance: ['dgm_compliance', 'agm_vigilance'] as Role[],
  audit: AUDIT_VIEWERS,
  models: ['data_science_lead', 'it_admin'] as Role[],
  reporting: REPORTING_VIEWERS,
  org: ORG_VIEWERS,
  admin: ['it_admin'] as Role[],
}

export function navItemsForRole(role: Role | null): NavItem[] {
  if (!role) return []
  return NAV_ITEMS.filter((item) => item.roles.includes(role))
}
