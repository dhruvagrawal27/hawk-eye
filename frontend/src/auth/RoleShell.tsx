import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './rbac'
import type { Capability } from './capabilities'
import type { Role } from '@/lib/types'

/**
 * Role-scoped route shell (FRONTEND-3). Wraps a route subtree and renders it only for the permitted
 * roles / capability per the Part 24.1 matrix; otherwise redirects to /forbidden. Defense-in-depth —
 * the server enforces authoritatively. Used in the router to gate each persona's screens.
 */
export function RoleShell({ roles, capability }: { roles?: Role[]; capability?: Capability }) {
  const { role, can } = useAuth()
  if (!role) return <Navigate to="/login" replace />
  if (roles && !roles.includes(role)) return <Navigate to="/forbidden" replace />
  if (capability && !can(capability)) return <Navigate to="/forbidden" replace />
  return <Outlet />
}
