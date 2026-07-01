/**
 * Local auth mode (Agent 3) — sign in against the backend's `HAWKEYE_AUTH_MODE=local` directory
 * (POST /api/v1/auth/login {username,password}) with NO Keycloak/OIDC. This is the path a deployed
 * live URL uses when no IdP is running: a persona/username picker POSTs credentials and we store the
 * returned short-lived JWT in the AuthProvider session, exactly like the OIDC path does after callback.
 *
 * The access token's `role` claim is mapped onto the app Role union via the shared ROLE_CLAIM_MAP,
 * so backend role identities line up with the RBAC matrix. We decode the JWT locally (no extra
 * round-trip) rather than reading the response's untyped `role` field.
 */
import { apiClient } from '@/lib/apiClient'
import type { AuthUser, Role } from '@/lib/types'
import { ROLE_CLAIM_MAP } from './oidc'

/** Shared local-mode password (backend seed). Usernames are the EMP-* directory below. */
export const LOCAL_PASSWORD = 'hawk-eye'

/**
 * Persona directory for the local sign-in picker — one valid backend username per human Role.
 * Usernames + display names mirror the backend user_store seed so audit "who-did-what" lines up.
 * Order follows the org chart (RM → MD&CEO → IT).
 */
export interface LocalPersona {
  role: Role
  username: string
  name: string
}

export const LOCAL_PERSONAS: LocalPersona[] = [
  { role: 'relationship_manager', username: 'EMP-rm01', name: 'Asha Nair' },
  { role: 'branch_manager', username: 'EMP-bm01', name: 'Sunil Rao' },
  { role: 'cluster_head', username: 'EMP-ch01', name: 'Priya Deshmukh' },
  { role: 'agm_vigilance', username: 'EMP-agm1', name: 'Tara Iyer' },
  { role: 'dgm_compliance', username: 'EMP-dgm1', name: "Carla D'Souza" },
  { role: 'data_science_lead', username: 'EMP-ds01', name: 'Maya Krishnan' },
  { role: 'cgm_risk', username: 'EMP-cgm1', name: 'Vikram Rao' },
  { role: 'chief_internal_auditor', username: 'EMP-cia1', name: 'Anil Verma' },
  { role: 'executive_director', username: 'EMP-ed01', name: 'Lakshmi Menon' },
  { role: 'managing_director', username: 'EMP-md01', name: 'Rajan Pillai' },
  { role: 'it_admin', username: 'EMP-it01', name: 'Pat Sharma' },
]

/** base64url → JSON object; returns null on any malformed segment (never throws). */
function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = b64.length % 4 === 0 ? '' : '='.repeat(4 - (b64.length % 4))
    const json = atob(b64 + pad)
    const parsed = JSON.parse(json) as unknown
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, unknown>) : null
  } catch {
    return null
  }
}

/** Map the token's `role` claim (and `sub`/`name`) onto an AuthUser, falling back to `username`. */
function userFromToken(token: string, username: string): AuthUser {
  const claims = decodeJwtPayload(token) ?? {}
  const rawRole = typeof claims['role'] === 'string' ? (claims['role'] as string) : undefined
  const mapped = rawRole ? ROLE_CLAIM_MAP[rawRole] : undefined
  const sub = typeof claims['sub'] === 'string' ? (claims['sub'] as string) : username
  const name = typeof claims['name'] === 'string' ? (claims['name'] as string) : username
  return {
    sub,
    username,
    name,
    roles: mapped ? [mapped] : ['relationship_manager'],
  }
}

export interface LocalLoginResult {
  user: AuthUser
  token: string
  expiresIn: number
}

/**
 * Authenticate against the backend local directory. Throws (propagating apiClient's ApiError) on
 * bad credentials so the caller can surface a message; the AuthProvider stores the token on success.
 */
export async function localLogin(
  username: string,
  password: string = LOCAL_PASSWORD,
): Promise<LocalLoginResult> {
  const token = await apiClient.login({ username, password })
  return {
    user: userFromToken(token.access_token, username),
    token: token.access_token,
    expiresIn: token.expires_in,
  }
}
