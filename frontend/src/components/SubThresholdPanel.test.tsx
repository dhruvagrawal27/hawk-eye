/**
 * Phase 4 — Sub-threshold ('hidden 95%') visibility. The panel surfaces the detection funnel and
 * the near-miss watchlist (scored-but-not-alerted, < 70) that the alert queue never shows.
 */
import { describe, expect, it } from 'vitest'
import { renderWithProviders, waitFor } from '@/test/utils'
import { SubThresholdPanel } from '@/components/SubThresholdPanel'

describe('SubThresholdPanel', () => {
  it('renders the detection funnel and the near-miss watchlist', async () => {
    const { getByText, findByText } = renderWithProviders(<SubThresholdPanel />)
    await findByText(/Ambient activity/i)
    // funnel stages appear once the query resolves
    await waitFor(() => getByText('Scored by the full stack'))
    expect(getByText(/Sub-threshold .* recorded, not alerted/i)).toBeTruthy()
    expect(getByText('Surfaced as alerts')).toBeTruthy()
    // the "only N% clears the bar" callout is the headline insight
    expect(getByText(/clears the 70 bar/i)).toBeTruthy()
    // a watchlist near-miss entity (elevated, not alerted)
    expect(getByText('EMP-2b14')).toBeTruthy()
  })
})
