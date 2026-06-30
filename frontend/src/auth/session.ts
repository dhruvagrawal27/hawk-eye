import { useEffect, useRef } from 'react'
import { env } from '@/lib/env'

/**
 * Session controls (FRONTEND-2): idle-timeout auto-logout and refresh-before-expiry. The access
 * token lives in memory (authToken.ts) and a reload deliberately drops it; these hooks keep an
 * active session fresh and end an inactive one.
 */

const ACTIVITY_EVENTS = [
  'mousedown',
  'keydown',
  'scroll',
  'touchstart',
  'visibilitychange',
] as const

/** Logs out after `timeoutMs` of no user activity. Disabled when `enabled` is false. */
export function useIdleLogout(
  onIdle: () => void,
  enabled: boolean,
  timeoutMs = env.idleTimeoutMinutes * 60_000,
) {
  const onIdleRef = useRef(onIdle)
  onIdleRef.current = onIdle

  useEffect(() => {
    if (!enabled) return
    let timer: ReturnType<typeof setTimeout>
    const reset = () => {
      clearTimeout(timer)
      timer = setTimeout(() => onIdleRef.current(), timeoutMs)
    }
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, reset, { passive: true }))
    reset()
    return () => {
      clearTimeout(timer)
      ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, reset))
    }
  }, [enabled, timeoutMs])
}

/**
 * Schedules a refresh ~60s before the access token expires (refresh-before-expiry). Re-arms whenever
 * `expiresAt` changes (i.e. after each successful refresh). No-op if there is no expiry.
 */
export function useRefreshBeforeExpiry(
  expiresAt: number | null,
  onRefresh: () => void,
  enabled: boolean,
) {
  const onRefreshRef = useRef(onRefresh)
  onRefreshRef.current = onRefresh

  useEffect(() => {
    if (!enabled || !expiresAt) return
    const lead = 60_000
    const delay = Math.max(5_000, expiresAt - Date.now() - lead)
    const timer = setTimeout(() => onRefreshRef.current(), delay)
    return () => clearTimeout(timer)
  }, [expiresAt, enabled])
}
