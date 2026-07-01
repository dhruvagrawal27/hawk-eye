import { describe, expect, it } from 'vitest'
import { handlers } from '@/lib/mocks/handlers'
import { server } from '@/lib/mocks/server'
import { listSourceFiles } from './sourceFiles'

/**
 * INVARIANT #5/#6 — MSW MOCKS INTACT (durable guard).
 *
 * "Keep MSW mocks." / "the app runs end-to-end on MSW (VITE_USE_MOCKS=true) with no backend."
 * (HAWK-EYE_UI_UPLIFT_PROMPTS.md). The whole UI-uplift is verified on mocks, so if a restyle deletes or
 * hollows out the handler set, every screen silently loses its data. This guard asserts the MSW server +
 * handler set stay wired and still cover the routes the worked-burst case walks end-to-end.
 */
describe('MSW mocks · server + handler set stay wired', () => {
  it('exports a usable node server', () => {
    expect(server).toBeTruthy()
    expect(typeof server.listen).toBe('function')
    expect(typeof server.use).toBe('function')
  })

  it('registers a non-trivial handler set', () => {
    expect(Array.isArray(handlers)).toBe(true)
    expect(handlers.length).toBeGreaterThan(20)
  })

  it('covers every route the worked-burst investigation walks', () => {
    const src = listSourceFiles({ includeMocks: true }).find(
      (f) => f.rel === 'lib/mocks/handlers.ts',
    )
    expect(src, 'lib/mocks/handlers.ts must exist').toBeTruthy()
    const text = src!.text
    const required = [
      '/alerts',
      '/alerts/:id',
      '/alerts/:id/disposition',
      '/alerts/:id/block-request',
      '/entities/:id',
      '/entities/:id/unmask',
      '/explanations/:id',
      '/narratives/:id',
      '/audit',
      '/cases',
    ]
    const missing = required.filter((r) => !text.includes(`'${r}'`) && !text.includes(`"${r}"`))
    expect(missing, `MSW handlers no longer cover: ${missing.join(', ')}`).toEqual([])
  })
})
