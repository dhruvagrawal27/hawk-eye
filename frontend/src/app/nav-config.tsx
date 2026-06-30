import {
  LayoutDashboard,
  Inbox,
  FolderKanban,
  Scale,
  FileSearch,
  Boxes,
  BarChart3,
  ServerCog,
  type LucideIcon,
} from 'lucide-react'
import type { Role } from '@/lib/types'

/**
 * Navigation + route-access map. The Sidebar filters items by the active role and the router gates
 * each screen with the same role set (RoleShell) — defense-in-depth over the Part 24.1 matrix.
 * Role sets are derived from the 8 personas/screens in Part 24.4.
 */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles: Role[]
  /** Blueprint screen number (Part 24.4) for traceability. */
  screen?: number
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: '/',
    label: 'Dashboard',
    icon: LayoutDashboard,
    roles: [
      'analyst',
      'senior_investigator',
      'team_lead',
      'compliance_officer',
      'auditor',
      'model_engineer',
      'platform_admin',
    ],
  },
  {
    to: '/triage',
    label: 'Triage queue',
    icon: Inbox,
    roles: ['analyst', 'senior_investigator', 'team_lead'],
    screen: 2,
  },
  {
    to: '/cases',
    label: 'Cases',
    icon: FolderKanban,
    roles: ['analyst', 'senior_investigator', 'team_lead'],
    screen: 4,
  },
  {
    to: '/compliance',
    label: 'Compliance',
    icon: Scale,
    roles: ['compliance_officer', 'team_lead'],
    screen: 5,
  },
  {
    to: '/audit',
    label: 'Auditor',
    icon: FileSearch,
    roles: ['auditor', 'team_lead', 'compliance_officer', 'platform_admin'],
    screen: 6,
  },
  {
    to: '/models',
    label: 'Model engineer',
    icon: Boxes,
    roles: ['model_engineer', 'platform_admin'],
    screen: 7,
  },
  {
    to: '/reporting',
    label: 'Reporting & KRIs',
    icon: BarChart3,
    roles: ['team_lead', 'compliance_officer', 'auditor', 'platform_admin'],
  },
  { to: '/admin', label: 'Admin', icon: ServerCog, roles: ['platform_admin'], screen: 8 },
]

/** Role sets per gated route, reused by the router's RoleShell guards. */
export const ROUTE_ROLES = {
  triageAndCases: ['analyst', 'senior_investigator', 'team_lead'] as Role[],
  caseDetailViewers: [
    'analyst',
    'senior_investigator',
    'team_lead',
    'compliance_officer',
  ] as Role[],
  compliance: ['compliance_officer', 'team_lead'] as Role[],
  audit: ['auditor', 'team_lead', 'compliance_officer', 'platform_admin'] as Role[],
  models: ['model_engineer', 'platform_admin'] as Role[],
  reporting: ['team_lead', 'compliance_officer', 'auditor', 'platform_admin'] as Role[],
  admin: ['platform_admin'] as Role[],
}

export function navItemsForRole(role: Role | null): NavItem[] {
  if (!role) return []
  return NAV_ITEMS.filter((item) => item.roles.includes(role))
}
