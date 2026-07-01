/**
 * Phase 2 — Rich explainability. The L4 sequence attention must render as the full LAXCAT
 * variable×temporal heatmap (which variable, at which step) rather than a single temporal bar.
 */
import { describe, expect, it } from 'vitest'
import { renderWithProviders } from '@/test/utils'
import { AttentionHeatmap, hasVariableAttention } from '@/components/AttentionHeatmap'
import { AttentionView } from '@/components/AttentionView'
import type { AttentionSession } from '@/lib/types'

const session: AttentionSession = {
  session_id: 'sess_55e1',
  model: 'LAXCAT',
  steps: [
    {
      event_id: 'evt_a',
      ts: '2026-06-30T02:14:07Z',
      label: 'create_beneficiary',
      verb: 'create_beneficiary',
      weight: 0.74,
      is_off_hours: true,
      variables: [
        { name: 'verb', weight: 0.82 },
        { name: 'log_amount', weight: 0.61 },
        { name: 'off_hours', weight: 0.83 },
      ],
    },
    {
      event_id: 'evt_b',
      ts: '2026-06-30T02:33:10Z',
      label: 'approve_payment',
      verb: 'approve_payment',
      weight: 0.9,
      is_off_hours: true,
      variables: [
        { name: 'verb', weight: 0.9 },
        { name: 'log_amount', weight: 0.88 },
        { name: 'off_hours', weight: 0.9 },
      ],
    },
  ],
}

const barsOnly: AttentionSession = {
  session_id: 'sess_x',
  model: 'LAXCAT',
  steps: [{ ts: '2026-06-30T02:14:07Z', label: 'login', verb: 'login', weight: 0.2 }],
}

describe('AttentionHeatmap — variable × temporal', () => {
  it('detects per-variable attention', () => {
    expect(hasVariableAttention([session])).toBe(true)
    expect(hasVariableAttention([barsOnly])).toBe(false)
  })

  it('renders variable rows and the LAXCAT model label', () => {
    const { getByText, getAllByRole } = renderWithProviders(<AttentionHeatmap sessions={[session]} />)
    getByText('LAXCAT')
    getByText('Verb')
    getByText('Log Amount')
    getByText('Off Hours')
    // header row + one row per variable (3 variables here)
    expect(getAllByRole('row').length).toBeGreaterThanOrEqual(4)
  })

  it('AttentionView promotes to the heatmap when variables are present', () => {
    const { getByText } = renderWithProviders(<AttentionView sessions={[session]} />)
    // the heatmap caption is unique to the matrix view
    getByText(/Rows = variables/i)
  })

  it('AttentionView keeps the temporal bar view when no variables are present', () => {
    const { getByText, queryByText } = renderWithProviders(<AttentionView sessions={[barsOnly]} />)
    expect(queryByText(/Rows = variables/i)).toBeNull()
    getByText(/Bar height/i)
  })
})
