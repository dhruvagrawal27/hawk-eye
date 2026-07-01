/**
 * Phase 5 — Management analytics. The typology panel ranks insider typologies by prevalence and
 * shows a confirmed-rate ("% real") and exposure per typology — the portfolio oversight view.
 */
import { describe, expect, it } from 'vitest'
import { renderWithProviders, waitFor } from '@/test/utils'
import { TypologyAnalytics } from '@/components/TypologyAnalytics'

describe('TypologyAnalytics', () => {
  it('renders typologies ranked by prevalence with confirmed-rate + exposure', async () => {
    const { getByText, getAllByText, findByText } = renderWithProviders(
      <TypologyAnalytics />,
      { role: 'agm_vigilance' },
    )
    await findByText(/Fraud typologies/i)
    await waitFor(() => getByText('New-beneficiary → high-value approve'))
    getByText('Maker-checker collusion ring')
    // confirmed-rate pills render as "NN% real"
    expect(getAllByText(/% real/).length).toBeGreaterThan(0)
    // totals summary (appears alongside the header eyebrow)
    expect(getAllByText(/confirmed-rate/i).length).toBeGreaterThan(0)
  })
})
