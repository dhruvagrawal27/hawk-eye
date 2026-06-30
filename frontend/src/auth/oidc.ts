/**
 * OIDC / Keycloak integration (FRONTEND-2). Authorization-Code + **PKCE** against Keycloak 25.x
 * (issuer + client read from env — never hardcoded). The access token is kept **in memory**
 * (authToken.ts) — the OIDC `User` is stored in an in-memory store, never localStorage — so a reload
 * drops the token and silent re-auth re-establishes it. MFA is enforced by the IdP redirect; this
 * code surfaces the redirect step, it does not implement factors.
 *
 * Real-IdP paths (signinRedirect/callback/logout) require a provisioned Keycloak realm/client
 * (PLATFORM/BACKEND) and are exercised when `VITE_USE_MOCKS=false`. In mock/dev the LoginPage uses a
 * role picker (simulated SSO+MFA) so the whole console runs with no IdP.
 */
import type { UserManager, User } from 'oidc-client-ts'
import { env } from '@/lib/env'
import type { AuthUser, Role } from '@/lib/types'

/** In-memory Storage shim so oidc-client-ts never persists the user/token to localStorage. */
class InMemoryStorage implements Storage {
  private map = new Map<string, string>()
  get length() {
    return this.map.size
  }
  clear(): void {
    this.map.clear()
  }
  getItem(key: string): string | null {
    return this.map.has(key) ? (this.map.get(key) as string) : null
  }
  key(index: number): string | null {
    return Array.from(this.map.keys())[index] ?? null
  }
  removeItem(key: string): void {
    this.map.delete(key)
  }
  setItem(key: string, value: string): void {
    this.map.set(key, value)
  }
}

let manager: UserManager | null = null

/** Lazily construct the UserManager (keeps oidc-client-ts out of the initial bundle). */
export async function getUserManager(): Promise<UserManager> {
  if (manager) return manager
  const { UserManager, WebStorageStateStore } = await import('oidc-client-ts')
  manager = new UserManager({
    authority: env.oidc.authority,
    client_id: env.oidc.clientId,
    redirect_uri: env.oidc.redirectUri,
    post_logout_redirect_uri: env.oidc.postLogoutRedirectUri,
    response_type: 'code', // Authorization Code + PKCE
    scope: env.oidc.scope,
    loadUserInfo: true,
    automaticSilentRenew: false, // refresh goes through BACKEND POST /auth/refresh
    // PKCE redirect state must survive the round-trip → sessionStorage (transient, not the token).
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    // The user/token is NOT persisted (security posture: token in memory only).
    userStore: new WebStorageStateStore({ store: new InMemoryStorage() }),
  })
  return manager
}

export async function signinRedirect(): Promise<void> {
  const um = await getUserManager()
  await um.signinRedirect()
}

export async function handleSigninCallback(): Promise<User> {
  const um = await getUserManager()
  return um.signinRedirectCallback()
}

export async function signoutRedirect(): Promise<void> {
  const um = await getUserManager()
  await um.signoutRedirect()
}

/** Map IdP role claims (Keycloak realm_access.roles / a `roles` claim) onto our Role union. */
const ROLE_CLAIM_MAP: Record<string, Role> = {
  analyst: 'analyst',
  l1_investigator: 'analyst',
  senior_investigator: 'senior_investigator',
  senior: 'senior_investigator',
  team_lead: 'team_lead',
  mlro: 'team_lead',
  compliance_officer: 'compliance_officer',
  compliance: 'compliance_officer',
  auditor: 'auditor',
  model_engineer: 'model_engineer',
  data_scientist: 'model_engineer',
  platform_admin: 'platform_admin',
  admin: 'platform_admin',
  service_account: 'service_account',
}

export function mapClaimsToUser(user: User): AuthUser {
  const profile = user.profile as Record<string, unknown>
  const realmAccess = (profile['realm_access'] as { roles?: string[] } | undefined)?.roles ?? []
  const rolesClaim = (profile['roles'] as string[] | undefined) ?? []
  const raw = [...realmAccess, ...rolesClaim]
  const roles = Array.from(
    new Set(raw.map((r) => ROLE_CLAIM_MAP[r]).filter((r): r is Role => Boolean(r))),
  )
  return {
    sub: user.profile.sub,
    username: (profile['preferred_username'] as string) ?? user.profile.sub,
    name:
      (user.profile.name as string) ?? (profile['preferred_username'] as string) ?? 'Investigator',
    email: user.profile.email,
    roles: roles.length ? roles : ['analyst'],
  }
}
