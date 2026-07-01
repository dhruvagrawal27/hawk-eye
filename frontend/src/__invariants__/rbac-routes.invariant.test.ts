import { describe, expect, it } from 'vitest'
import { NAV_ITEMS, ROUTE_ROLES, navItemsForRole } from '@/app/nav-config'
import { can, canViewCaseData, HUMAN_ROLES, type Capability, type Role } from '@/auth/capabilities'

/**
 * INVARIANT #4 — RBAC / SoD, NO WIDENING (durable guard).
 *
 * "Preserve the roles × capabilities gating and role-appropriate views. A redesign must not widen
 *  anyone's access or expose routes a role can't use." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * `capabilities.test.ts` already pins the MATRIX itself (12 roles × 9 caps). This guard pins the *route*
 * and *nav* layer against that matrix: it fails if the router's `ROUTE_ROLES` or the sidebar `NAV_ITEMS`
 * ever grant a role a screen its capability forbids — the way a UI restyle would most plausibly leak
 * access (adding a role to a nav list, loosening a RoleShell guard).
 */

/** Case-data (PII-bearing) routes: every listed role must be allowed to view case data. */
const CASE_DATA_ROUTES: (keyof typeof ROUTE_ROLES)[] = [
  'triageAndCases',
  'caseDetailViewers',
  'compliance',
]

/** Routes gated on a single hard capability — every listed role must hold it. */
const CAP_GATED_ROUTES: { key: keyof typeof ROUTE_ROLES; capability: Capability }[] = [
  { key: 'triageAndCases', capability: 'triage' },
  { key: 'audit', capability: 'view_audit' },
  { key: 'models', capability: 'train_models' },
  { key: 'admin', capability: 'admin' },
]

/** Sidebar path → the RoleShell route-role set it must stay consistent with (defense-in-depth). */
const NAV_ROUTE_ALIGNMENT: { path: string; key: keyof typeof ROUTE_ROLES }[] = [
  { path: '/triage', key: 'triageAndCases' },
  { path: '/cases', key: 'triageAndCases' },
  { path: '/compliance', key: 'compliance' },
  { path: '/audit', key: 'audit' },
  { path: '/models', key: 'models' },
  { path: '/admin', key: 'admin' },
  { path: '/graph', key: 'graph' },
  { path: '/org', key: 'org' },
  { path: '/replay', key: 'replay' },
]

describe('RBAC route guards · no widening', () => {
  it('case-data routes admit only roles permitted to view case data (no de-identified/none roles)', () => {
    for (const key of CASE_DATA_ROUTES) {
      const leaks = ROUTE_ROLES[key].filter((r) => !canViewCaseData(r))
      expect(leaks, `${key} exposes case data to non-case-data roles: ${leaks.join(', ')}`).toEqual(
        [],
      )
    }
  })

  it('capability-gated routes admit only roles that hold the capability', () => {
    for (const { key, capability } of CAP_GATED_ROUTES) {
      const leaks = ROUTE_ROLES[key].filter((r) => !can(r, capability))
      expect(leaks, `${key} admits roles lacking '${capability}': ${leaks.join(', ')}`).toEqual([])
    }
  })

  it('the admin console is restricted to it_admin', () => {
    expect([...ROUTE_ROLES.admin].sort()).toEqual(['it_admin'])
  })

  it('never grants the non-interactive service_account access to any route', () => {
    for (const [key, roles] of Object.entries(ROUTE_ROLES)) {
      expect(
        (roles as Role[]).includes('service_account'),
        `service_account must not reach ${key}`,
      ).toBe(false)
    }
  })
})

describe('RBAC nav · sidebar aligns with route guards', () => {
  it('every gated nav item is a subset of its RoleShell route roles', () => {
    for (const { path, key } of NAV_ROUTE_ALIGNMENT) {
      const item = NAV_ITEMS.find((n) => n.to === path)
      expect(item, `nav item for ${path} must exist`).toBeTruthy()
      const allowed = new Set<Role>(ROUTE_ROLES[key])
      const leaks = item!.roles.filter((r) => !allowed.has(r))
      expect(
        leaks,
        `sidebar shows ${path} to roles the route forbids: ${leaks.join(', ')}`,
      ).toEqual([])
    }
  })

  it('a role only ever sees nav items its own role list contains (no cross-role leakage)', () => {
    for (const role of HUMAN_ROLES) {
      for (const item of navItemsForRole(role)) {
        expect(item.roles).toContain(role)
      }
    }
  })

  it('roles without case-data access never see triage/cases in their sidebar', () => {
    const caseNavPaths = new Set(['/triage', '/cases'])
    for (const role of HUMAN_ROLES) {
      if (canViewCaseData(role)) continue
      const leaked = navItemsForRole(role).filter((i) => caseNavPaths.has(i.to))
      expect(
        leaked.map((i) => i.to),
        `${role} must not see case-data nav`,
      ).toEqual([])
    }
  })
})
