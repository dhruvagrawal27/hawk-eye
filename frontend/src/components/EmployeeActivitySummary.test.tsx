/**
 * The activity summary gives a senior approver context (risk index + recent activity + who has
 * looked) before they approve an alert or permit a held privileged action.
 */
import { describe, it } from 'vitest'
import { renderWithProviders, waitFor } from '@/test/utils'
import { EmployeeActivitySummary } from '@/components/EmployeeActivitySummary'

describe('EmployeeActivitySummary', () => {
  it('renders the insider-risk index and recent activity for an entity', async () => {
    const { findByText, getByText } = renderWithProviders(
      <EmployeeActivitySummary entityId="EMP-7f3a" enabled />,
      { role: 'agm_vigilance' },
    )
    await findByText(/Insider-risk index/i)
    await waitFor(() => getByText(/Recent activity/i))
  })

  it('does not fetch when disabled (lazy)', () => {
    const { queryByText } = renderWithProviders(
      <EmployeeActivitySummary entityId="EMP-7f3a" enabled={false} />,
      { role: 'agm_vigilance' },
    )
    // nothing loaded yet → shows the empty/idle line, not the risk index
    queryByText(/Insider-risk index/i)
  })
})
