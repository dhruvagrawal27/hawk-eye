import { useCallback, useEffect, useMemo, useState } from 'react'
import { env } from '@/lib/env'
import { apiClient } from '@/lib/apiClient'
import {
  clearAccessToken,
  getTokenExpiry,
  setAccessToken,
  setUnauthorizedHandler,
} from '@/lib/authToken'
import type { AuthUser, Role } from '@/lib/types'
import { AuthContext, type AuthContextValue } from './rbac'
import {
  can as matrixCan,
  constraintFor as matrixConstraint,
  canViewCaseData as matrixCanViewCaseData,
  ROLE_META,
} from './capabilities'
import { handleSigninCallback, mapClaimsToUser, signinRedirect, signoutRedirect } from './oidc'
import { LOCAL_PERSONAS, localLogin } from './localAuth'
import { useIdleLogout, useRefreshBeforeExpiry } from './session'

/**
 * Demo identities for mock SSO — one per bank org-chart role (docs/BANK_ROLES.md demo personas).
 * Usernames match the audit fixtures so "who-did-what" lines up. Covers all 12 roles (11 human +
 * 1 service); the human roles are surfaced in the login persona picker via HUMAN_ROLES.
 */
const DEMO_USERS: Record<Role, AuthUser> = {
  relationship_manager: {
    sub: 'mock-rm',
    username: 'rm.demo',
    name: 'Asha Iyer',
    email: 'rm@bank.local',
    roles: ['relationship_manager'],
  },
  branch_manager: {
    sub: 'mock-branch',
    username: 'branch.demo',
    name: 'Rohan Das',
    email: 'branch@bank.local',
    roles: ['branch_manager'],
  },
  cluster_head: {
    sub: 'mock-cluster',
    username: 'cluster.demo',
    name: 'Vikas Shah',
    email: 'cluster@bank.local',
    roles: ['cluster_head'],
  },
  agm_vigilance: {
    sub: 'mock-agm',
    username: 'agm.demo',
    name: 'Kavita Menon',
    email: 'agm@bank.local',
    roles: ['agm_vigilance'],
  },
  dgm_compliance: {
    sub: 'mock-dgm',
    username: 'dgm.demo',
    name: 'Suresh Pillai',
    email: 'dgm@bank.local',
    roles: ['dgm_compliance'],
  },
  data_science_lead: {
    sub: 'mock-datasci',
    username: 'datasci.demo',
    name: 'Anil Kumar',
    email: 'datasci@bank.local',
    roles: ['data_science_lead'],
  },
  cgm_risk: {
    sub: 'mock-cgm',
    username: 'cgm.demo',
    name: 'Lakshmi Rao',
    email: 'cgm@bank.local',
    roles: ['cgm_risk'],
  },
  chief_internal_auditor: {
    sub: 'mock-cia',
    username: 'cia.demo',
    name: 'Meera Joshi',
    email: 'cia@bank.local',
    roles: ['chief_internal_auditor'],
  },
  executive_director: {
    sub: 'mock-ed',
    username: 'ed.demo',
    name: 'Ravi Khanna',
    email: 'ed@bank.local',
    roles: ['executive_director'],
  },
  managing_director: {
    sub: 'mock-md',
    username: 'md.demo',
    name: 'Sunil Verma',
    email: 'md@bank.local',
    roles: ['managing_director'],
  },
  it_admin: {
    sub: 'mock-itadmin',
    username: 'itadmin.demo',
    name: 'Platform Admin',
    email: 'itadmin@bank.local',
    roles: ['it_admin'],
  },
  service_account: {
    sub: 'mock-svc',
    username: 'service.ingest',
    name: 'Ingest Service',
    roles: ['service_account'],
  },
}

const DEMO_ROLE_KEY = 'hawkeye.demo_role'
/** Persisted local-mode username so a soft re-mount (not a hard reload) re-mints the same session. */
const LOCAL_USER_KEY = 'hawkeye.local_username'

/** role → backend username for the local persona picker (POST /auth/login credentials). */
const LOCAL_USERNAME_BY_ROLE = Object.fromEntries(
  LOCAL_PERSONAS.map((p) => [p.role, p.username]),
) as Partial<Record<Role, string>>

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const isMock = env.useMocks
  const isLocal = env.authMode === 'local'
  const [status, setStatus] = useState<AuthContextValue['status']>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [activeRole, setActiveRole] = useState<Role | null>(null)
  const [expiresAt, setExpiresAt] = useState<number | null>(null)

  const applyUser = useCallback((u: AuthUser, token: string, expiresIn: number) => {
    setAccessToken(token, expiresIn)
    setExpiresAt(getTokenExpiry())
    setUser(u)
    setActiveRole(u.roles[0] ?? 'relationship_manager')
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    clearAccessToken()
    setUser(null)
    setActiveRole(null)
    setExpiresAt(null)
    setStatus('unauthenticated')
    sessionStorage.removeItem(DEMO_ROLE_KEY)
    sessionStorage.removeItem(LOCAL_USER_KEY)
    // Only the real IdP path needs an end-session redirect; mock/local clear state in-place.
    if (env.authMode === 'oidc') {
      try {
        await signoutRedirect()
      } catch {
        /* best-effort — local state already cleared */
      }
    }
  }, [])

  const login = useCallback(
    async (role?: Role) => {
      if (isMock) {
        const r = role ?? 'relationship_manager'
        const token = await apiClient
          .login({ username: DEMO_USERS[r].username })
          .catch(() => ({ access_token: 'mock.jwt', expires_in: 900 }))
        sessionStorage.setItem(DEMO_ROLE_KEY, r)
        applyUser(DEMO_USERS[r], token.access_token, token.expires_in)
        return
      }
      if (isLocal) {
        // Local mode: the picked persona maps to a real backend username; POST credentials and
        // store the returned JWT (role taken from the token's claims). No Keycloak/OIDC redirect.
        const r = role ?? 'relationship_manager'
        const username = LOCAL_USERNAME_BY_ROLE[r] ?? LOCAL_PERSONAS[0].username
        const { user, token, expiresIn } = await localLogin(username)
        sessionStorage.setItem(LOCAL_USER_KEY, username)
        applyUser(user, token, expiresIn)
        return
      }
      await signinRedirect()
    },
    [isMock, isLocal, applyUser],
  )

  const refresh = useCallback(async () => {
    try {
      const token = await apiClient.refresh()
      setAccessToken(token.access_token, token.expires_in)
      setExpiresAt(getTokenExpiry())
    } catch {
      await logout()
    }
  }, [logout])

  /** Called by CallbackPage after the OIDC redirect returns (real IdP path). */
  const completeSigninCallback = useCallback(async () => {
    const oidcUser = await handleSigninCallback()
    const authUser = mapClaimsToUser(oidcUser)
    applyUser(authUser, oidcUser.access_token, oidcUser.expires_in ?? 900)
  }, [applyUser])

  // Restore on mount: mock re-mints a token for the persisted demo role; local re-mints from the
  // persisted username (fixed dev password); real waits for the OIDC callback/explicit login.
  useEffect(() => {
    if (isMock) {
      const saved = sessionStorage.getItem(DEMO_ROLE_KEY) as Role | null
      if (saved && DEMO_USERS[saved]) {
        void login(saved)
        return
      }
    } else if (isLocal) {
      const savedUser = sessionStorage.getItem(LOCAL_USER_KEY)
      const persona = savedUser ? LOCAL_PERSONAS.find((p) => p.username === savedUser) : undefined
      if (persona) {
        void login(persona.role)
        return
      }
    }
    setStatus('unauthenticated')
  }, [isMock, isLocal, login])

  // 401 → end the session (server is authoritative; client guard is defense-in-depth).
  useEffect(() => {
    setUnauthorizedHandler(() => {
      void logout()
    })
    return () => setUnauthorizedHandler(null)
  }, [logout])

  useIdleLogout(() => void logout(), status === 'authenticated')
  useRefreshBeforeExpiry(expiresAt, () => void refresh(), status === 'authenticated')

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      role: activeRole,
      roles: user?.roles ?? [],
      isMock,
      login,
      completeSignin: completeSigninCallback,
      setActiveRole: (r: Role) => {
        setActiveRole(r)
        // Demo convenience: switching the active role re-mints the matching identity (mock token,
        // or a fresh local-mode login for the persona that holds that role).
        if (isMock || isLocal) void login(r)
      },
      logout,
      can: (cap) => matrixCan(activeRole ?? undefined, cap),
      constraintFor: (cap) => matrixConstraint(activeRole ?? undefined, cap),
      canViewCaseData: matrixCanViewCaseData(activeRole ?? undefined),
    }),
    [status, user, activeRole, isMock, isLocal, login, logout, completeSigninCallback],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export { ROLE_META }
