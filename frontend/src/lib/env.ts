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

export const env = {
  /** BACKEND REST base, includes `/api/v1` (BACKEND.md §3). */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
  /** When true, MSW serves the typed apiClient against Part 24.5 fixtures (no backend needed). */
  useMocks: readBool(import.meta.env.VITE_USE_MOCKS, false),
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
  /** Realtime stream endpoint (used by WsRealtimeSource once the backend exposes /ws). */
  wsBaseUrl:
    import.meta.env.VITE_WS_BASE_URL ??
    `${window.location.origin.replace(/^http/, 'ws')}/ws/alerts`,
  /** Idle auto-logout window (FRONTEND-2 session controls). */
  idleTimeoutMinutes: readNumber(import.meta.env.VITE_IDLE_TIMEOUT_MINUTES, 15),
  mode: import.meta.env.MODE,
  isDev: import.meta.env.DEV,
} as const
