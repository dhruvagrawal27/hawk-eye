import { createContext, useContext, type ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { AuthUser, Role } from '@/lib/types'
import { Spinner } from '@/components/ui/spinner'
import {
  can as matrixCan,
  constraintFor as matrixConstraint,
  canViewCaseData as matrixCanViewCaseData,
  type Capability,
} from './capabilities'

/**
 * Auth + RBAC context and guards. Client-side guards are **defense-in-depth** (the server is
 * authoritative — prompt §3/§7); they keep forbidden routes and controls out of the UI per the
 * Part 24.1 matrix. AuthProvider (separate file) supplies the value.
 */
export interface AuthContextValue {
  status: 'loading' | 'unauthenticated' | 'authenticated'
  user: AuthUser | null
  /** The active role (a user may hold several; the demo can switch among them). */
  role: Role | null
  roles: Role[]
  isMock: boolean
  login: (role?: Role) => Promise<void>
  /** Completes the OIDC redirect exchange (real IdP path; called by CallbackPage). */
  completeSignin: () => Promise<void>
  setActiveRole: (role: Role) => void
  logout: () => Promise<void>
  /** Whether the active role holds a capability at all (✅ or ⚠️) per the matrix. */
  can: (capability: Capability) => boolean
  /** The ⚠️ constraint string for a capability (case-scoped, logged, …), if any. */
  constraintFor: (capability: Capability) => string | undefined
  /** Whether the active role may view PII-bearing case data. */
  canViewCaseData: boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}

/** Convenience: read a single capability for the active role. */
export function useCan(capability: Capability): boolean {
  return useAuth().can(capability)
}

/** Pure helpers re-exported so non-context callers (tests, mocks) can reason about a role. */
export const rbac = {
  can: matrixCan,
  constraintFor: matrixConstraint,
  canViewCaseData: matrixCanViewCaseData,
}

/* ── Route guard: must be authenticated ─────────────────────────────────── */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}

/* ── Control guard: render children only if the active role holds a capability ── */
export function Can({
  capability,
  children,
  fallback = null,
}: {
  capability: Capability
  children: ReactNode
  fallback?: ReactNode
}) {
  const { can } = useAuth()
  return <>{can(capability) ? children : fallback}</>
}
