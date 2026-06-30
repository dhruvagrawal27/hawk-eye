import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SlaTimer } from './SlaTimer'

/** SLA test (§8): the timer warns/breaches correctly relative to sla_due_ts. */
describe('<SlaTimer>', () => {
  const now = new Date('2026-06-30T00:00:00Z')

  it('shows an ok state ~30 days out (worked-burst alert)', () => {
    render(<SlaTimer dueTs="2026-07-30T02:41:55Z" now={now} />)
    expect(screen.getByText(/left/i).closest('[data-sla-state]')).toHaveAttribute(
      'data-sla-state',
      'ok',
    )
  })

  it('flags urgent within 72h', () => {
    render(<SlaTimer dueTs="2026-07-01T00:00:00Z" now={now} />)
    expect(screen.getByText(/left/i).closest('[data-sla-state]')).toHaveAttribute(
      'data-sla-state',
      'urgent',
    )
  })

  it('flags breached past due', () => {
    render(<SlaTimer dueTs="2026-06-28T00:00:00Z" now={now} />)
    expect(screen.getByText(/breached/i).closest('[data-sla-state]')).toHaveAttribute(
      'data-sla-state',
      'breached',
    )
  })
})
