/**
 * Display density (study Phase 0.7). Compact = 24px-ish rows for power-user triage;
 * comfortable = default. Persisted to localStorage and applied as `data-density` on <html>,
 * which CSS reads (`:root[data-density='compact'] { --row-py }`). useSyncExternalStore keeps
 * every consumer in sync without a global store dependency.
 */
import { useSyncExternalStore } from 'react'

export type Density = 'comfortable' | 'compact'

const KEY = 'hawkeye:density'
const listeners = new Set<() => void>()

function read(): Density {
  if (typeof localStorage === 'undefined') return 'comfortable'
  return localStorage.getItem(KEY) === 'compact' ? 'compact' : 'comfortable'
}

function apply(d: Density): void {
  if (typeof document !== 'undefined') document.documentElement.dataset.density = d
}

/** Call once at boot so the persisted choice is reflected before first paint. */
export function initDensity(): void {
  apply(read())
}

export function setDensity(d: Density): void {
  if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, d)
  apply(d)
  listeners.forEach((l) => l())
}

export function toggleDensity(): void {
  setDensity(read() === 'compact' ? 'comfortable' : 'compact')
}

export function useDensity(): [Density, (d: Density) => void] {
  const density = useSyncExternalStore(
    (cb) => {
      listeners.add(cb)
      return () => listeners.delete(cb)
    },
    read,
    () => 'comfortable' as Density,
  )
  return [density, setDensity]
}
