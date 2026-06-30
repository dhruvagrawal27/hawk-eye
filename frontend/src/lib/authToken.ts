/**
 * In-memory access-token holder (FRONTEND-2 security posture: short-lived JWT kept **in memory**,
 * never in localStorage). The HTTP layer reads the token from here; the auth/session layer writes it.
 * Keeping it in a tiny non-React module avoids an auth→lib circular import and means a page reload
 * deliberately drops the token (silent re-auth via OIDC re-establishes it).
 */

interface TokenState {
  accessToken: string | null
  /** epoch ms when the access token expires (for refresh-before-expiry scheduling). */
  expiresAt: number | null
}

const state: TokenState = { accessToken: null, expiresAt: null }

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

export function setAccessToken(token: string | null, expiresInSeconds?: number): void {
  state.accessToken = token
  state.expiresAt = token && expiresInSeconds ? Date.now() + expiresInSeconds * 1000 : null
}

export function getAccessToken(): string | null {
  return state.accessToken
}

export function getTokenExpiry(): number | null {
  return state.expiresAt
}

export function clearAccessToken(): void {
  state.accessToken = null
  state.expiresAt = null
}

/** Registered by AuthProvider — invoked when the API returns 401 so the session can refresh/logout. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

export function notifyUnauthorized(): void {
  onUnauthorized?.()
}
