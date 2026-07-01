import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderWithProviders, screen } from '@/test/utils'
import { server } from '@/lib/mocks/server'
import { ExplanationPanel } from '@/components/ExplanationPanel'

/**
 * INVARIANT #2 — CONTESTABILITY / NATURAL JUSTICE (durable guard).
 *
 * "Every alert view must render its reason codes + narrative. An alert with no reasons is invalid —
 *  surface that, never hide reasons behind a flourish." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * This guard pins the two halves of the invariant on the explanation surface: (1) a valid alert shows
 * its reason codes (rule provenance section renders), and (2) when no explanation is available the panel
 * shows an explicit, labelled state with a retry — never a blank region a flourish could hide behind.
 */
describe('contestability · reason codes are always surfaced', () => {
  it('renders the labelled evidence sections + reason codes for a valid alert', async () => {
    renderWithProviders(<ExplanationPanel alertId="alr_3d7e22" />, { role: 'relationship_manager' })
    // The panel is always framed as contestable evidence…
    expect(await screen.findByText(/why this alert fired/i)).toBeInTheDocument()
    expect(screen.getByText(/SAR \/ FMR-defensible/i)).toBeInTheDocument()
    // …and the deterministic reason codes (rule provenance) render, not just the AI narrative.
    expect(await screen.findByText(/rule provenance/i)).toBeInTheDocument()
  })

  it('surfaces an explicit invalid state (never blank) when no explanation is available', async () => {
    server.use(http.get('*/explanations/*', () => new HttpResponse(null, { status: 404 })))
    renderWithProviders(<ExplanationPanel alertId="alr_missing" />, {
      role: 'relationship_manager',
    })
    // The section header is always present (the region is never blank)…
    expect(await screen.findByText(/why this alert fired/i)).toBeInTheDocument()
    // …and the failure is surfaced explicitly with a retry affordance, not silently hidden.
    expect(await screen.findByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
