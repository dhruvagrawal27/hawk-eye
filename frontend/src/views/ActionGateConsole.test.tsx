import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('@/auth/rbac', () => ({ useAuth: () => ({ user: { username: 'EMP-boss' } }) }))

import { ActionGateConsole } from './ActionGateConsole'
import type { ActionHold, ActionPolicy } from '@/lib/types'

const HOLD: ActionHold = {
  hold_id: 'hold_1',
  request_id: 'req_1',
  subject: 'EMP-3c55',
  verb: 'self_grant',
  status: 'pending_review',
  severity: 'high',
  reason_codes: [{ source: 'policy', code: 'SELF_GRANT_HOLD', detail: 'self-grant' }],
  proportionality: 'reversible staff action held pending review',
  explanation: 'DBA self-grant in a privileged session',
  dpia_binding: true,
  decider: null,
  justification: null,
  outcome: null,
  ts: '2026-06-30T02:41:00Z',
}
const POLICY: ActionPolicy = {
  code: 'SELF_GRANT_HOLD', name: 'Entitlement self-grant', gate: 'hard',
  severity: 'high', enabled: true, verbs: ['self_grant'],
}

function renderConsole() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ActionGateConsole />
    </QueryClientProvider>,
  )
}

describe('ActionGateConsole', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('renders the HOLD queue + policies + alert-only framing', async () => {
    const { apiClient } = await import('@/lib/apiClient')
    vi.spyOn(apiClient, 'listActionHolds').mockResolvedValue({ items: [HOLD], count: 1 })
    vi.spyOn(apiClient, 'listActionPolicies').mockResolvedValue([POLICY])
    renderConsole()
    await waitFor(() => expect(screen.getByText('EMP-3c55')).toBeInTheDocument())
    expect(screen.getByText(/permits human-initiated execution|never auto-executes/i)).toBeInTheDocument()
    expect(screen.getByText(/Entitlement self-grant/i)).toBeInTheDocument()
  })

  it('four-eyes approve calls decideActionHold with a justification', async () => {
    const { apiClient } = await import('@/lib/apiClient')
    vi.spyOn(apiClient, 'listActionHolds').mockResolvedValue({ items: [HOLD], count: 1 })
    vi.spyOn(apiClient, 'listActionPolicies').mockResolvedValue([])
    const decide = vi
      .spyOn(apiClient, 'decideActionHold')
      .mockResolvedValue({ ...HOLD, status: 'approved_via_four_eyes' })
    vi.spyOn(window, 'prompt').mockReturnValue('reviewed & permitted')
    renderConsole()
    await waitFor(() => expect(screen.getByText('EMP-3c55')).toBeInTheDocument())
    screen.getByRole('button', { name: /approve/i }).click()
    await waitFor(() =>
      expect(decide).toHaveBeenCalledWith('hold_1', {
        decider: 'EMP-boss',
        approve: true,
        justification: 'reviewed & permitted',
      }),
    )
  })
})
