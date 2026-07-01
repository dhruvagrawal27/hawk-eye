import { Navigate, Outlet } from 'react-router-dom'
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
  if (!role) return <Navigate to="/login" replace />
  const home = ROLE_META[role]?.defaultRoute ?? '/'
  if (roles && !roles.includes(role)) return <Navigate to={home} replace />
  if (capability && !can(capability)) return <Navigate to={home} replace />
  return <Outlet />
}
