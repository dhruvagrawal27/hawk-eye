import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './rbac'
import { ROLE_META, type Capability } from './capabilities'
import type { Role } from '@/lib/types'

/**
 * Role-scoped route shell (FRONTEND-3). Wraps a route subtree and renders it only for the permitted
 * roles / capability per the Part 24.1 matrix; otherwise sends the user to the route THEIR active
 * role lands on (ROLE_META.defaultRoute), never a dead "no access" page. This matters when a user
 * switches role while on a screen the new role can't see (e.g. Graph Explorer): the nav drops the
 * item AND the open route bounces them to their own home. Defense-in-depth — the server enforces
 * authoritatively.
 */
export function RoleShell({ roles, capability }: { roles?: Role[]; capability?: Capability }) {
  const { role, can } = useAuth()
  const location = useLocation()
  if (!role) return <Navigate to="/login" replace />
  const denied = (roles && !roles.includes(role)) || (capability && !can(capability))
  if (!denied) return <Outlet />
  // Bounce the user to their own home. Loop-proofing: if home resolves back to the current path
  // (a misconfigured defaultRoute that itself is denied), fall back to the always-reachable
  // Dashboard so a denied route can never infinite-redirect and freeze the app.
  const home = ROLE_META[role]?.defaultRoute ?? '/'
  const target = home === location.pathname ? '/' : home
  return <Navigate to={target} replace />
}
