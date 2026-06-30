import { describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'
import { MaskedPII } from './MaskedPII'
import { renderWithProviders, screen, waitFor } from '@/test/utils'

/**
 * PII test (§8): default render shows the token; the audited unmask control appears only for roles
 * with the unmask capability and calls POST /entities/{id}/unmask, surfacing that it is logged.
 */
describe('<MaskedPII> — default-mask + audited unmask (Part 25.3)', () => {
  it('shows the tokenized id by default', () => {
    renderWithProviders(<MaskedPII value="EMP-7f3a" entityId="EMP-7f3a" />, { role: 'analyst' })
    expect(screen.getByText('EMP-7f3a')).toBeInTheDocument()
  })

  it('exposes an audited unmask control for a permitted role and reveals the value', async () => {
    const user = userEvent.setup()
    renderWithProviders(<MaskedPII value="EMP-7f3a" entityId="EMP-7f3a" alertId="alr_3d7e22" />, {
      role: 'senior_investigator',
    })
    const btn = screen.getByLabelText(/unmask EMP-7f3a/i)
    await user.click(btn)
    await waitFor(() => expect(screen.getByText(/Arjun Mehta/)).toBeInTheDocument())
    expect(screen.getByText(/logged/i)).toBeInTheDocument()
  })

  it('hides the unmask control for a role without the capability (auditor)', () => {
    renderWithProviders(<MaskedPII value="EMP-7f3a" entityId="EMP-7f3a" />, { role: 'auditor' })
    expect(screen.getByText('EMP-7f3a')).toBeInTheDocument()
    expect(screen.queryByLabelText(/unmask EMP-7f3a/i)).not.toBeInTheDocument()
  })
})
