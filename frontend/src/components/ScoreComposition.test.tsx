/**
 * Phase 1 — Detection Transparency. The score-composition panel must render the *real* 5-layer
 * decomposition the backend now serves: every layer (incl. the rule floor L1 and sequence L4), the
 * cross-layer agreement, and a decisive-layer-aware "rescued by …" counterfactual driven by the
 * backend's own `rescued`/`decisive_layer` flags (not a client-side guess).
 */
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { ScoreComposition, computeRescued } from '@/components/ScoreComposition'
import { deriveLayerBreakdown } from '@/lib/layerFusion'
import type { Alert, FusionBreakdown } from '@/lib/types'

function fusion(overrides: Partial<FusionBreakdown> = {}): FusionBreakdown {
  return {
    fused: 0.9,
    threshold: 0.7,
    calibrated_score: 90,
    agreement: 0.56,
    confidence: 0.86,
    hard_hit: false,
    rescued: true,
    decisive_layer: 'L5_graph',
    meta_version: 'l6_meta@stub-2026.06.30',
    components: [
      { layer: 'L1_rule', label: 'Rules / BRE', sublabel: 'L1 · deterministic', proba: 0.4, weight: 1.7, contribution: 0.68 },
      { layer: 'L2_unsupervised', label: 'Anomaly', sublabel: 'L2 · unsupervised', proba: 0.55, weight: 1.2, contribution: 0.66 },
      { layer: 'L3_gbdt', label: 'Gradient-boosted trees', sublabel: 'L3 · supervised tabular', proba: 0.62, weight: 2.4, contribution: 1.488 },
      { layer: 'L4_sequence', label: 'Sequence', sublabel: 'L4 · attention', proba: null, weight: 1.0, contribution: 0 },
      { layer: 'L5_graph', label: 'Graph / collusion', sublabel: 'L5 · GNN', proba: 1.0, weight: 1.2, contribution: 1.2 },
    ],
    ...overrides,
  }
}

describe('ScoreComposition — 5-layer decomposition', () => {
  it('renders every detection layer including the L1 rule floor and L4 sequence', () => {
    const { getByText } = render(<ScoreComposition fusion={fusion()} />)
    getByText('Rules / BRE')
    getByText('Anomaly')
    getByText('Gradient-boosted trees')
    getByText('Sequence')
    getByText('Graph / collusion')
  })

  it('shows cross-layer agreement and the decisive-layer rescue callout', () => {
    const { getByText } = render(<ScoreComposition fusion={fusion()} />)
    getByText('Cross-layer agreement')
    getByText('Rescued by Graph / collusion') // decisive_layer = L5_graph
  })

  it('marks a layer that did not run', () => {
    const { getByText } = render(<ScoreComposition fusion={fusion()} />)
    getByText('did not fire') // L4 sequence proba is null
  })
})

describe('computeRescued honours the backend arithmetic', () => {
  it('trusts an explicit backend rescued=true', () => {
    expect(computeRescued(fusion({ rescued: true }))).toBe(true)
  })
  it('trusts an explicit backend rescued=false even if GBDT is under threshold', () => {
    expect(computeRescued(fusion({ rescued: false }))).toBe(false)
  })
})

describe('deriveLayerBreakdown normalises L1_rule↔L1_rules and uses the backend threshold', () => {
  const alert = {
    contributing_layers: ['L1_rules', 'L2_unsupervised', 'L3_gbdt', 'L5_graph'],
    risk_score: 90,
  } as unknown as Alert

  it('maps the backend L1_rule component onto the L1_rules layer row', () => {
    const b = deriveLayerBreakdown(alert, fusion())
    const l1 = b.layers.find((l) => l.layer === 'L1_rules')
    expect(l1?.fired).toBe(true)
    expect(l1?.proba).toBe(0.4) // picked up from the backend component, not synthesised
  })

  it('adopts the backend decision threshold (0.7 → 70) and rescued/agreement flags', () => {
    const b = deriveLayerBreakdown(alert, fusion())
    expect(b.threshold).toBe(70)
    expect(b.rescued).toBe(true)
    expect(b.decisive?.layer).toBe('L5_graph')
    expect(b.agreement).toBe(0.56)
  })
})
