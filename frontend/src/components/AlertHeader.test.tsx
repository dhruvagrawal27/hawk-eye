import { describe, expect, it } from 'vitest'
import { renderWithProviders, screen } from '@/test/utils'
import { AlertHeader } from '@/components/AlertHeader'
import type { Alert, ReasonCode } from '@/lib/types'

/**
 * CONTESTABILITY at the top of the case file (invariant #2). The uplifted header carries a reason-code
 * preview so an investigator sees *why* before acting — and an alert with no reasons is surfaced as
 * explicitly invalid, never as a blank header a visual flourish could hide behind.
 */
function makeAlert(reason_codes: ReasonCode[]): Alert {
  return {
    alert_id: 'alr_test01',
    entity_id: 'EMP-test',
    risk_score: 87,
    severity: 'high',
    confidence: 0.82,
    status: 'open',
    created_ts: '2026-06-30T02:41:55Z',
    contributing_layers: ['L1_rules', 'L3_gbdt'],
    reason_codes,
    exposure_inr: 4_800_000,
    sla_due_ts: '2026-07-20T00:00:00Z',
    pii_tokenized: true,
  }
}

describe('AlertHeader · contestability is visible at the top of the case file', () => {
  it('renders the reason-code preview for a valid alert', () => {
    const alert = makeAlert([
      {
        source: 'rule',
        code: 'NEW_BENEFICIARY_THEN_HIGHVALUE',
        detail: 'new payee then high value',
      },
      { source: 'shap', feature: 'minutes_since_new_beneficiary', contribution: 0.41 },
    ])
    renderWithProviders(<AlertHeader alert={alert} />, { role: 'relationship_manager' })
    expect(screen.getByText('NEW_BENEFICIARY_THEN_HIGHVALUE')).toBeInTheDocument()
    expect(screen.getByText('minutes_since_new_beneficiary')).toBeInTheDocument()
  })

  it('surfaces an explicit "no reason codes — invalid" state (never blank) when reasons are empty', () => {
    renderWithProviders(<AlertHeader alert={makeAlert([])} />, { role: 'relationship_manager' })
    expect(screen.getByText(/no reason codes/i)).toBeInTheDocument()
    expect(screen.getByText(/alert invalid/i)).toBeInTheDocument()
  })
})
