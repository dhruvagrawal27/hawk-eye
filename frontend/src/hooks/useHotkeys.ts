/**
 * Keyboard layer (study: terminal-grade keyboard control). Two hooks:
 *  - useGlobalHotkeys: app-wide bindings (⌘/Ctrl-K opens the palette). One window listener, stable
 *    handler held in a ref so we never rebind on every render.
 *  - useListHotkeys: opt-in table/list nav (j/k move, e open, x toggle, '/' focus search) that
 *    consumers wire to their own row state.
 *
 * Both ignore keystrokes while the user is typing in a field (input/textarea/select/contentEditable)
 * so single-letter hotkeys don't fight with text entry.
 */
import { useEffect, useRef } from 'react'

/** True when focus is in a text-entry surface — single-letter hotkeys must yield to typing. */
export function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  return el.isContentEditable === true
}

/** True for ⌘ (mac) or Ctrl (others) — the platform command modifier. */
function isCommandModifier(e: KeyboardEvent): boolean {
  return e.metaKey || e.ctrlKey
}

export interface GlobalHotkeysOptions {
  /** Open (or toggle) the command palette — bound to ⌘/Ctrl-K. */
  onPalette: () => void
}

/**
 * Bind app-global hotkeys for the component's lifetime. Safe to mount once (in the shell). The handler
 * is read from a ref, so passing a fresh `onPalette` each render does not tear down the listener.
 */
export function useGlobalHotkeys({ onPalette }: GlobalHotkeysOptions): void {
  const onPaletteRef = useRef(onPalette)
  onPaletteRef.current = onPalette

  useEffect(() => {
    function handle(e: KeyboardEvent): void {
      // ⌘K / Ctrl-K — allowed even while typing (it's a modified chord, not a letter hotkey).
      if (isCommandModifier(e) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        onPaletteRef.current()
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [])
}

export interface ListHotkeysOptions {
  /** j / ArrowDown — move selection to the next row. */
  onNext: () => void
  /** k / ArrowUp — move selection to the previous row. */
  onPrev: () => void
  /** e / Enter — open/inspect the active row. */
  onOpen: () => void
  /** x — toggle selection/flag on the active row. */
  onToggle?: () => void
  /** '/' — focus the list's search box. */
  onSearch?: () => void
  /** Disable all bindings (e.g. while a modal is open). */
  enabled?: boolean
}

/**
 * Opt-in list/table navigation. Mount inside the list view and pass handlers that mutate that view's
 * own selection state. Ignores keystrokes while typing, and ignores modified chords so it never
 * shadows browser/global shortcuts. Handlers are ref-held so the listener is bound once.
 */
export function useListHotkeys(opts: ListHotkeysOptions): void {
  const ref = useRef(opts)
  ref.current = opts

  useEffect(() => {
    function handle(e: KeyboardEvent): void {
      const o = ref.current
      if (o.enabled === false) return
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return

      switch (e.key) {
        case 'j':
        case 'ArrowDown':
          e.preventDefault()
          o.onNext()
          break
        case 'k':
        case 'ArrowUp':
          e.preventDefault()
          o.onPrev()
          break
        case 'e':
        case 'Enter':
          e.preventDefault()
          o.onOpen()
          break
        case 'x':
          if (o.onToggle) {
            e.preventDefault()
            o.onToggle()
          }
          break
        case '/':
          if (o.onSearch) {
            e.preventDefault()
            o.onSearch()
          }
          break
        default:
          break
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [])
}
