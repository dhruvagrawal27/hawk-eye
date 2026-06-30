import { describe, expect, it } from 'vitest'
import { renderWithProviders, screen } from '@/test/utils'
import { SAMPLE_ALERT } from '@/lib/mocks/fixtures'
import { AlertHeader } from '@/components/AlertHeader'
import { EddActionPanel } from '@/components/EddActionPanel'
import { ExplanationPanel } from '@/components/ExplanationPanel'
import { AiNarrative } from '@/components/AiNarrative'

/**
 * Render-level contract tests (§8): the investigation panels render the **Part 24.5 worked-burst
 * payload** without error, reason codes render, the AI narrative is labelled + degrades honestly,
 * and the alert-only / SoD invariants hold in the actual DOM.
 */

describe('AlertHeader renders the sample alert (Part 24.5b)', () => {
  it('shows risk, entity token and exposure', () => {
    renderWithProviders(<AlertHeader alert={SAMPLE_ALERT} />, { role: 'analyst' })
    expect(screen.getByText('87')).toBeInTheDocument()
    expect(screen.getByText('EMP-7f3a')).toBeInTheDocument()
    expect(screen.getByText('₹48,00,000')).toBeInTheDocument()
  })
})

describe('Explanation panel (Part 11 / Part 24.5)', () => {
  it('renders rule provenance and the labelled AI narrative', async () => {
    renderWithProviders(<ExplanationPanel alertId="alr_3d7e22" />, { role: 'analyst' })
    expect(await screen.findByText(/NEW_BENEFICIARY_THEN_HIGHVALUE/i)).toBeInTheDocument()
    expect(await screen.findByText(/AI-generated/i)).toBeInTheDocument()
  })
})

describe('AI narrative degradation (Part 25)', () => {
  it('renders the deterministic template honestly as Not TEE-attested', async () => {
    renderWithProviders(<AiNarrative alertId="alr_4d88" />, { role: 'analyst' })
    expect(await screen.findByText(/AI-generated/i)).toBeInTheDocument()
    expect(await screen.findByText(/not tee-attested/i)).toBeInTheDocument()
  })
})

describe('EDD panel — alert-only + RBAC/SoD invariants', () => {
  it('analyst sees disposition + a *request*-block (never an auto-block)', () => {
    renderWithProviders(<EddActionPanel alert={SAMPLE_ALERT} />, { role: 'analyst' })
    expect(screen.getByRole('button', { name: /mark fraud/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /request block/i })).toBeInTheDocument()
    // Alert-only: no control that blocks money outright.
    expect(screen.queryByRole('button', { name: /^block$/i })).not.toBeInTheDocument()
    expect(screen.getByText(/never auto-blocks|routed to a Team Lead/i)).toBeInTheDocument()
  })

  it('model engineer cannot disposition (SoD Part 19.6) — controls absent', () => {
    renderWithProviders(<EddActionPanel alert={SAMPLE_ALERT} />, { role: 'model_engineer' })
    expect(screen.queryByRole('button', { name: /mark fraud/i })).not.toBeInTheDocument()
    expect(screen.getByText(/separation of duties|read-only/i)).toBeInTheDocument()
  })

  it('auditor (read-only) sees no mutation controls', () => {
    renderWithProviders(<EddActionPanel alert={SAMPLE_ALERT} />, { role: 'auditor' })
    expect(screen.queryByRole('button', { name: /mark fraud/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /request block/i })).not.toBeInTheDocument()
  })
})
