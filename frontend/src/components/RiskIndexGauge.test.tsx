import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RiskIndexGauge } from './RiskIndexGauge'
import type { RiskIndex } from '@/lib/types'

const INDEX: RiskIndex = {
  employee_id: 'EMP-7f3a',
  composite: 78,
  hr_score: 0.55,
  access_score: 0.48,
  anomaly_score: 0.72,
  components: [{ name: 'offhours_score', group: 'anomaly', value: 0.72, detail: 'off-hours' }],
  top_drivers: ['offhours_score', 'role_change_recency'],
  updated_ts: '2026-06-30T06:00:00Z',
  calibrated: false,
}

describe('RiskIndexGauge', () => {
  it('renders the composite, sub-scores, drivers and the alert-only note', async () => {
    const { apiClient } = await import('@/lib/apiClient')
    vi.spyOn(apiClient, 'getRiskIndex').mockResolvedValue(INDEX)
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <RiskIndexGauge entityId="EMP-7f3a" />
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByLabelText(/insider risk 78 of 100/i)).toBeInTheDocument(),
    )
    expect(screen.getByText(/insider-risk index/i)).toBeInTheDocument()
    expect(screen.getByText(/uncalibrated/i)).toBeInTheDocument()
    expect(screen.getByText(/alert-only/i)).toBeInTheDocument()
    // the "how this score was computed" breakdown is present
    expect(screen.getByText(/how this 78 was computed/i)).toBeInTheDocument()
  })

  it('renders nothing when the entity has no index (404)', async () => {
    const { apiClient } = await import('@/lib/apiClient')
    vi.spyOn(apiClient, 'getRiskIndex').mockRejectedValue(new Error('404'))
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { container } = render(
      <QueryClientProvider client={qc}>
        <RiskIndexGauge entityId="EMP-none" />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(container.querySelector('.size-16')).toBeNull())
  })
})
