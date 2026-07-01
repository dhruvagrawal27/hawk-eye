import { afterEach, describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'
import { renderWithProviders, screen, waitFor } from '@/test/utils'
import { MaskedPII } from '@/components/MaskedPII'
import { apiClient } from '@/lib/apiClient'

/**
 * INVARIANT #3 — WATCH THE WATCHERS / AUDITED UNMASK (durable guard).
 *
 * "Every PII unmask stays audited. Keep the audit calls; make the 'this view was logged' feedback
 *  visible to the user." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * `MaskedPII.test.tsx` proves the reveal shows the value + a "logged" cue. This guard adds the part that
 * matters most and is easiest to regress during a restyle: unmasking must actually fire the server-side
 * audit call (`POST /entities/{id}/unmask`) — a purely-visual "peel" that forgot the network call would
 * silently break watch-the-watchers. A's re-skin may change the animation; it must not change this.
 */
describe('audited unmask · the reveal fires the server-side audit call', () => {
  afterEach(() => vi.restoreAllMocks())

  it('calls apiClient.unmaskEntity and shows the "logged" feedback on reveal', async () => {
    const user = userEvent.setup()
    // Spy that still calls through, so MSW responds and the "logged" toast/cue renders.
    const spy = vi.spyOn(apiClient, 'unmaskEntity')

    renderWithProviders(<MaskedPII value="EMP-7f3a" entityId="EMP-7f3a" alertId="alr_3d7e22" />, {
      role: 'branch_manager',
    })

    // Masked by default (tokenized).
    expect(screen.getByText('EMP-7f3a')).toBeInTheDocument()

    await user.click(screen.getByLabelText(/unmask EMP-7f3a/i))

    // The audit-bearing call fired for this entity/token…
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    expect(spy).toHaveBeenCalledWith(
      'EMP-7f3a',
      expect.objectContaining({ tokens: ['EMP-7f3a'], alert_id: 'alr_3d7e22' }),
    )
    // …and the user is told the view was logged.
    expect(await screen.findByText(/logged/i)).toBeInTheDocument()
  })

  it('offers no unmask affordance to a role without unmask_pii (no silent widening)', () => {
    const spy = vi.spyOn(apiClient, 'unmaskEntity')
    renderWithProviders(<MaskedPII value="EMP-7f3a" entityId="EMP-7f3a" />, {
      role: 'chief_internal_auditor',
    })
    expect(screen.queryByLabelText(/unmask EMP-7f3a/i)).not.toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })
})
