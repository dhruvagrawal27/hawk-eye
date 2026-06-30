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
import { useIdleLogout, useRefreshBeforeExpiry } from './session'

/** Demo identities for mock SSO — usernames match the audit fixtures so "who-did-what" lines up. */
const DEMO_USERS: Record<Role, AuthUser> = {
  analyst: {
    sub: 'mock-analyst',
    username: 'analyst.demo',
    name: 'Asha Iyer',
    email: 'analyst@bank.local',
    roles: ['analyst'],
  },
  senior_investigator: {
    sub: 'mock-senior',
    username: 'senior.demo',
    name: 'Rohan Das',
    email: 'senior@bank.local',
    roles: ['senior_investigator'],
  },
  team_lead: {
    sub: 'mock-mlro',
    username: 'mlro.demo',
    name: 'Kavita Menon',
    email: 'mlro@bank.local',
    roles: ['team_lead'],
  },
  compliance_officer: {
    sub: 'mock-compliance',
    username: 'compliance.demo',
    name: 'Suresh Pillai',
    email: 'compliance@bank.local',
    roles: ['compliance_officer'],
  },
  auditor: {
    sub: 'mock-auditor',
    username: 'auditor.demo',
    name: 'Meera Joshi',
    email: 'auditor@bank.local',
    roles: ['auditor'],
  },
  model_engineer: {
    sub: 'mock-modeleng',
    username: 'modeleng.demo',
    name: 'Anil Kumar',
    email: 'modeleng@bank.local',
    roles: ['model_engineer'],
  },
  platform_admin: {
    sub: 'mock-admin',
    username: 'admin.demo',
    name: 'Platform Admin',
    email: 'admin@bank.local',
    roles: ['platform_admin'],
  },
  service_account: {
    sub: 'mock-svc',
    username: 'service.ingest',
    name: 'Ingest Service',
    roles: ['service_account'],
  },
}

const DEMO_ROLE_KEY = 'hawkeye.demo_role'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const isMock = env.useMocks
  const [status, setStatus] = useState<AuthContextValue['status']>('loading')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [activeRole, setActiveRole] = useState<Role | null>(null)
  const [expiresAt, setExpiresAt] = useState<number | null>(null)

  const applyUser = useCallback((u: AuthUser, token: string, expiresIn: number) => {
    setAccessToken(token, expiresIn)
    setExpiresAt(getTokenExpiry())
    setUser(u)
    setActiveRole(u.roles[0] ?? 'analyst')
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    clearAccessToken()
    setUser(null)
    setActiveRole(null)
    setExpiresAt(null)
    setStatus('unauthenticated')
    sessionStorage.removeItem(DEMO_ROLE_KEY)
    if (!isMock) {
      try {
        await signoutRedirect()
      } catch {
        /* best-effort — local state already cleared */
      }
    }
  }, [isMock])

  const login = useCallback(
    async (role?: Role) => {
      if (isMock) {
        const r = role ?? 'analyst'
        const token = await apiClient
          .login({ username: DEMO_USERS[r].username })
          .catch(() => ({ access_token: 'mock.jwt', expires_in: 900 }))
        sessionStorage.setItem(DEMO_ROLE_KEY, r)
        applyUser(DEMO_USERS[r], token.access_token, token.expires_in)
        return
      }
      await signinRedirect()
    },
    [isMock, applyUser],
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

  // Restore on mount: mock re-mints a token for the persisted demo role; real waits for callback/login.
  useEffect(() => {
    if (isMock) {
      const saved = sessionStorage.getItem(DEMO_ROLE_KEY) as Role | null
      if (saved && DEMO_USERS[saved]) {
        void login(saved)
        return
      }
    }
    setStatus('unauthenticated')
  }, [isMock, login])

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
        // Demo-only convenience: switching the active role re-mints the matching mock identity.
        if (isMock) void login(r)
      },
      logout,
      can: (cap) => matrixCan(activeRole ?? undefined, cap),
      constraintFor: (cap) => matrixConstraint(activeRole ?? undefined, cap),
      canViewCaseData: matrixCanViewCaseData(activeRole ?? undefined),
    }),
    [status, user, activeRole, isMock, login, logout, completeSigninCallback],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export { ROLE_META }
