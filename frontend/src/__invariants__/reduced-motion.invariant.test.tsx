import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders, screen } from '@/test/utils'
import { AlertHeader } from '@/components/AlertHeader'
import { SAMPLE_ALERT } from '@/lib/mocks/fixtures'

/**
 * INVARIANT #7 — prefers-reduced-motion HONORED EVERYWHERE (durable guard).
 *
 * "Every animation must degrade to instant/opacity-only… a reduced-motion user gets a fully static,
 *  high-contrast, fully-usable UI." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * This unit guard forces `prefers-reduced-motion: reduce` on and asserts the core alert surface still
 * renders all of its information (score, entity, exposure) — i.e. the content lives in the DOM, not in
 * an animation a reduced-motion user would never see. The full audit (axe + "no transform/opacity
 * animation runs") lives in the Playwright a11y spec (`e2e/a11y.e2e.ts`); this is the fast in-process
 * floor that runs on every push.
 *
 * NOTE (Agent A): when `@/ui/motion`'s `useReducedMotionSafe()` lands, extend this guard to assert it
 * returns `true` here and that the signature primitives render their final value statically.
 */
describe('reduced motion · UI stays fully usable when motion is reduced', () => {
  const realMatchMedia = window.matchMedia

  afterEach(() => {
    window.matchMedia = realMatchMedia
    vi.restoreAllMocks()
  })

  function forceReducedMotion(): void {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: /prefers-reduced-motion:\s*reduce/.test(query),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia
  }

  it('reports the reduce preference to the app', () => {
    forceReducedMotion()
    expect(window.matchMedia('(prefers-reduced-motion: reduce)').matches).toBe(true)
  })

  it('renders the full worked-burst alert header content under reduced motion', () => {
    forceReducedMotion()
    renderWithProviders(<AlertHeader alert={SAMPLE_ALERT} />, { role: 'relationship_manager' })
    // All information is present as real DOM text — nothing is trapped behind a motion-only reveal.
    expect(screen.getByText('87')).toBeInTheDocument()
    expect(screen.getByText('EMP-7f3a')).toBeInTheDocument()
    expect(screen.getByText('₹48,00,000')).toBeInTheDocument()
  })
})
