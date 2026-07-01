/**
 * Motion foundation — "Daylight Forensics" (docs/ui/UI_UPLIFT.md §2).
 *
 * One motion vocabulary for the whole app, standardised on Motion (`motion/react`, v12) +
 * AutoAnimate for lists. Everything here is **`prefers-reduced-motion`-aware**: with reduced motion,
 * transforms/springs degrade to instant or opacity-only. `useReducedMotionSafe()` is the single gate;
 * every signature primitive calls it. Import from `@/ui`.
 */
import {
  LazyMotion,
  domAnimation,
  MotionConfig,
  m,
  type Variants,
  type Transition,
} from 'motion/react'
import { useAutoAnimate } from '@formkit/auto-animate/react'
import {
  useCallback,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
  type CSSProperties,
} from 'react'

export { m, LazyMotion, domAnimation }
export { AnimatePresence } from 'motion/react'

const REDUCE_QUERY = '(prefers-reduced-motion: reduce)'

function subscribeReducedMotion(onChange: () => void): () => void {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => {}
  const mq = window.matchMedia(REDUCE_QUERY)
  mq.addEventListener?.('change', onChange)
  return () => mq.removeEventListener?.('change', onChange)
}

function getReducedMotionSnapshot(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
  return window.matchMedia(REDUCE_QUERY).matches
}

/**
 * `true` when the user has asked the OS to reduce motion. Reads `matchMedia` directly (via
 * `useSyncExternalStore`) rather than Motion's cached hook, so it stays live and is deterministically
 * controllable in tests. The single gate every signature primitive uses to degrade to instant.
 */
export function useReducedMotionSafe(): boolean {
  return useSyncExternalStore(subscribeReducedMotion, getReducedMotionSnapshot, () => false)
}

/**
 * App-root motion provider: LazyMotion (tree-shaken `domAnimation` features, consumed via `m.*`) +
 * MotionConfig honouring the OS reduced-motion setting for every descendant. Mount once, high in the tree.
 */
export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </LazyMotion>
  )
}

/* ─────────────────────────────── variants ─────────────────────────────── */

/** Route / page transition — a small rise + fade; reduced-motion collapses to fade only. */
export const pageVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
}

/** Staggered list reveal — parent orchestrates a 40ms cascade over its children. */
export const staggerParent: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } },
}
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.18, ease: 'easeOut' } },
}

/** Focus spotlight — a gentle lift used for the active dossier / selected row. */
export const spotlight: Variants = {
  rest: { scale: 1, opacity: 0.85 },
  active: { scale: 1.0, opacity: 1, transition: { duration: 0.16 } },
}

/** Springy but calm — the house transition for layout / shared-element moves. */
export const dossierSpring: Transition = { type: 'spring', stiffness: 150, damping: 20, mass: 0.6 }

/* ─────────────────────────────── RouteTransition ──────────────────────── */

/**
 * Wrap a routed screen so it enters with the page variant. Reduced-motion users get an instant,
 * opacity-only appearance (handled by MotionConfig + the variant's fade-only exit).
 */
export function RouteTransition({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const reduce = useReducedMotionSafe()
  return (
    <m.div
      className={className}
      initial={reduce ? { opacity: 0 } : 'hidden'}
      animate={reduce ? { opacity: 1 } : 'show'}
      variants={reduce ? undefined : pageVariants}
    >
      {children}
    </m.div>
  )
}

/* ─────────────────────────────── hooks ────────────────────────────────── */

/**
 * AutoAnimate for add/remove/reorder in lists (triage rows, timelines). Returns the ref to spread on
 * the list container. Honours reduced motion (AutoAnimate disables itself). Duration/easing tuned calm.
 */
export function useAutoAnimateList<T extends HTMLElement = HTMLElement>() {
  return useAutoAnimate<T>({ duration: 180, easing: 'ease-out' })
}

interface MagneticState {
  ref: React.RefObject<HTMLButtonElement | null>
  style: CSSProperties
  onMouseMove: (e: React.MouseEvent) => void
  onMouseLeave: () => void
}

/**
 * Magnetic CTA — the element drifts a few px toward the cursor, then springs home. No-op under reduced
 * motion (returns identity transform + no listeners doing work). Used by primary actions, sparingly.
 */
export function useMagnetic(strength = 6): MagneticState {
  const ref = useRef<HTMLButtonElement | null>(null)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const reduce = useReducedMotionSafe()

  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (reduce || !ref.current) return
      const rect = ref.current.getBoundingClientRect()
      const dx = e.clientX - (rect.left + rect.width / 2)
      const dy = e.clientY - (rect.top + rect.height / 2)
      setOffset({
        x: Math.max(-strength, Math.min(strength, (dx / rect.width) * strength * 2)),
        y: Math.max(-strength, Math.min(strength, (dy / rect.height) * strength * 2)),
      })
    },
    [reduce, strength],
  )

  const onMouseLeave = useCallback(() => setOffset({ x: 0, y: 0 }), [])

  return {
    ref,
    style: reduce
      ? {}
      : {
          transform: `translate(${offset.x}px, ${offset.y}px)`,
          transition: 'transform 150ms cubic-bezier(0.16,1,0.3,1)',
        },
    onMouseMove,
    onMouseLeave,
  }
}
