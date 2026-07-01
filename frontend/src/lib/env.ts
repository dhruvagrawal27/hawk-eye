/**
 * Typed, centralized access to Vite env (prompt §7: read issuer/client-id from env, never hardcode).
 * Components and the apiClient import from here — never `import.meta.env` directly — so config is a
 * single auditable seam and the mock/real switch is one flag.
 */

function readBool(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined) return fallback
  return value === 'true' || value === '1'
}

function readNumber(value: string | undefined, fallback: number): number {
  const n = value === undefined ? NaN : Number(value)
  return Number.isFinite(n) ? n : fallback
}

/**
 * Auth mode selection (Agent 3 — local login without Keycloak):
 *  - 'mock'  : VITE_USE_MOCKS=true → persona picker, MSW-served tokens, no backend/IdP.
 *  - 'oidc'  : real Keycloak Authorization-Code + PKCE (signinRedirect).
 *  - 'local' : backend HAWKEYE_AUTH_MODE=local — username/password POST /auth/login, no IdP.
 *
 * Explicit override via VITE_AUTH_MODE ('oidc' | 'local'). When unset we default to 'local'
 * for a live backend that has no OIDC authority configured (so a deployed URL can log in with
 * no Keycloak running), and 'oidc' when an authority IS explicitly provided. Mocks always win.
 */
function readOidcAuthorityConfigured(): boolean {
  const a = import.meta.env.VITE_OIDC_AUTHORITY
  return typeof a === 'string' && a.trim().length > 0
}

function resolveAuthMode(useMocks: boolean): 'mock' | 'oidc' | 'local' {
  if (useMocks) return 'mock'
  const explicit = import.meta.env.VITE_AUTH_MODE
  if (explicit === 'oidc' || explicit === 'local') return explicit
  return readOidcAuthorityConfigured() ? 'oidc' : 'local'
}

const useMocks = readBool(import.meta.env.VITE_USE_MOCKS, false)

/** Resolve a (possibly relative/http) realtime URL to an absolute ws(s):// URL. */
function resolveWs(value: string | undefined): string {
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const raw = value && value.length > 0 ? value : '/ws/alerts'
  if (/^wss?:\/\//.test(raw)) return raw
  if (/^https?:\/\//.test(raw)) return raw.replace(/^http/, 'ws')
  // relative path → origin (http→ws) + path
  return `${origin.replace(/^http/, 'ws')}${raw.startsWith('/') ? '' : '/'}${raw}`
}

export const env = {
  /** BACKEND REST base, includes `/api/v1` (BACKEND.md §3). */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  /** When true, MSW serves the typed apiClient against Part 24.5 fixtures (no backend needed). */
  useMocks,
  /**
   * How the frontend authenticates: 'mock' (persona picker), 'oidc' (Keycloak redirect), or
   * 'local' (backend username/password). Defaults to 'local' against a live backend with no OIDC
   * authority configured so the deployed URL can log in without Keycloak. See resolveAuthMode.
   */
  authMode: resolveAuthMode(useMocks),
  /** Keycloak 25.x OIDC (FRONTEND-2). */
  oidc: {
    authority: import.meta.env.VITE_OIDC_AUTHORITY ?? 'http://localhost:8080/realms/hawk-eye',
    clientId: import.meta.env.VITE_OIDC_CLIENT_ID ?? 'hawk-eye-console',
    redirectUri:
      import.meta.env.VITE_OIDC_REDIRECT_URI ?? `${window.location.origin}/auth/callback`,
    postLogoutRedirectUri:
      import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI ?? `${window.location.origin}/login`,
    scope: import.meta.env.VITE_OIDC_SCOPE ?? 'openid profile email',
  },
  /** Grafana 11.x ops dashboards, embedded in the Admin view (FRONTEND-13). */
  grafanaUrl: import.meta.env.VITE_GRAFANA_URL ?? 'http://localhost:3000',
  /** Realtime stream WebSocket URL (resolved to an absolute ws(s):// URL). VITE_WS_BASE_URL may be
   *  absolute (ws[s]://… or http[s]://…) or a relative path (/ws/alerts); empty → origin + /ws/alerts. */
  wsBaseUrl: resolveWs(import.meta.env.VITE_WS_BASE_URL),
  /** Idle auto-logout window (FRONTEND-2 session controls). */
  idleTimeoutMinutes: readNumber(import.meta.env.VITE_IDLE_TIMEOUT_MINUTES, 15),
  mode: import.meta.env.MODE,
  isDev: import.meta.env.DEV,
} as const
