/**
 * Deferred polish — per-layer score timeline. Decomposes the single fused line into one line per
 * detection layer over time (which layer saw it first), fed by GET /entities/{id}/layer-scores.
 */
import { describe, it } from 'vitest'
import { renderWithProviders, waitFor } from '@/test/utils'
import { LayerScoreTimeline } from '@/components/LayerScoreTimeline'

describe('LayerScoreTimeline', () => {
  it('renders the per-layer legend once the query resolves', async () => {
    const { getByText, findByText } = renderWithProviders(
      <LayerScoreTimeline entityId="EMP-7f3a" />,
    )
    await findByText(/Per-layer score timeline/i)
    // legend labels (below the chart) — one per detection layer
    await waitFor(() => getByText('Fused L6'))
    getByText('GBDT')
    getByText('Graph')
  })
})
