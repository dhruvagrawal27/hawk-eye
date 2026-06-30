/**
 * Command registry for the ⌘K palette (study: Bloomberg-style command surface). A Command is a flat,
 * declarative record; the palette renders them grouped and runs `perform(navigate)` on select. Nav
 * commands are derived from the single source of truth (`NAV_ITEMS` in app/nav-config) so the palette
 * never drifts from the sidebar. Actions (density, focus) are layered on top.
 *
 * Keep this UI-framework-thin: a Command knows nothing about cmdk/Radix — it only takes a `NavigateFn`
 * so it stays trivially testable and reusable from a keyboard shortcut or a button.
 */
import * as React from 'react'
import {
  Compass,
  Search,
  Rows3,
  Network,
  type LucideIcon,
} from 'lucide-react'
import { NAV_ITEMS } from '@/app/nav-config'
import { toggleDensity } from '@/lib/density'

/** Minimal navigation contract — satisfied by react-router's `useNavigate()` result. */
export type NavigateFn = (to: string) => void

export type CommandGroup = 'Navigation' | 'Actions'

export interface Command {
  /** Stable, unique id (also the cmdk value used for filtering/selection). */
  id: string
  title: string
  group: CommandGroup
  /** Extra terms folded into fuzzy matching (route, synonyms). */
  keywords?: string[]
  icon?: LucideIcon
  /** Run the command. Receives a navigate fn so it can route without owning a router dependency. */
  perform(nav: NavigateFn): void
}

/** Focus the triage queue's search box (id wired in views/TriageQueue). Navigates first if needed. */
function focusTriageSearch(nav: NavigateFn): void {
  nav('/triage')
  // Defer past the route transition / render so the input exists, then focus + select.
  const focus = (): void => {
    const el = document.getElementById('triage-search') as HTMLInputElement | null
    if (el) {
      el.focus()
      el.select?.()
    }
  }
  // Two rAFs ≈ next committed paint; cheap and avoids an arbitrary setTimeout race.
  requestAnimationFrame(() => requestAnimationFrame(focus))
}

/** Static action commands (not derived from nav). */
const ACTION_COMMANDS: Command[] = [
  {
    id: 'action:toggle-density',
    title: 'Toggle density (comfortable / compact)',
    group: 'Actions',
    keywords: ['density', 'compact', 'comfortable', 'rows', 'spacing'],
    icon: Rows3,
    perform: () => toggleDensity(),
  },
  {
    id: 'action:goto-org',
    title: 'Go to Org chart',
    group: 'Actions',
    keywords: ['org', 'chart', 'reporting tree', 'lines of defense'],
    icon: Network,
    perform: (nav) => nav('/org'),
  },
  {
    id: 'action:focus-triage-search',
    title: 'Focus triage search',
    group: 'Actions',
    keywords: ['search', 'triage', 'filter', 'find', 'queue'],
    icon: Search,
    perform: (nav) => focusTriageSearch(nav),
  },
]

/** Build the live command list. Nav commands come from `NAV_ITEMS`, so they stay in lockstep. */
export function useCommands(): Command[] {
  return React.useMemo<Command[]>(() => {
    const navCommands: Command[] = NAV_ITEMS.map((item) => ({
      id: `nav:${item.to}`,
      title: `Go to ${item.label}`,
      group: 'Navigation',
      keywords: [item.label, item.to, 'go', 'navigate'],
      icon: item.icon ?? Compass,
      perform: (nav) => nav(item.to),
    }))
    return [...navCommands, ...ACTION_COMMANDS]
  }, [])
}
