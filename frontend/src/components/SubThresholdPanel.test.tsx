/**
 * Phase 4 — Sub-threshold ('hidden 95%') visibility. The panel surfaces the detection funnel and
 * the near-miss watchlist (scored-but-not-alerted, < 70) that the alert queue never shows.
 */
import { describe, expect, it } from 'vitest'
import { renderWithProviders, waitFor } from '@/test/utils'
import { SubThresholdPanel } from '@/components/SubThresholdPanel'

describe('SubThresholdPanel', () => {
  it('renders the detection funnel and the watch list in plain English', async () => {
    const { getByText, findByText } = renderWithProviders(<SubThresholdPanel />)
    await findByText(/Watch list · activity just below the alert line/i)
    // funnel stages appear once the query resolves — stakeholder-friendly labels
    await waitFor(() => getByText('Actions screened this week'))
    expect(getByText(/Below the alert line — being watched/i)).toBeTruthy()
    expect(getByText('Raised as alerts')).toBeTruthy()
    // the headline callout is plain-language
    expect(getByText(/was alarming enough to alert/i)).toBeTruthy()
    // a watch-list entity still renders
    expect(getByText('EMP-2b14')).toBeTruthy()
  })
})
