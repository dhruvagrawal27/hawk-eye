import { describe, expect, it } from 'vitest'
import { apiClient } from '@/lib/apiClient'

/**
 * Contract tests — the typed apiClient (over MSW) returns the **exact Part 24.5 / BACKEND.md shapes**.
 * If BACKEND changes the contract, these break and we regenerate types. This is the data-level half
 * of §8 "contract tests"; the render-level half lives in the component contract tests.
 */
describe('Part 24.5(b) — sample alert alr_3d7e22', () => {
  it('matches the canonical alert shape field-for-field', async () => {
    const a = await apiClient.getAlert('alr_3d7e22')
    expect(a.alert_id).toBe('alr_3d7e22')
    expect(a.entity_id).toBe('EMP-7f3a')
    expect(a.risk_score).toBe(87)
    expect(a.severity).toBe('high')
    expect(a.confidence).toBe(0.82)
    expect(a.status).toBe('open')
    expect(a.contributing_layers).toEqual(['L1_rules', 'L2_unsupervised', 'L3_gbdt', 'L5_graph'])
    expect(a.exposure_inr).toBe(4800000)
    expect(a.sla_due_ts).toBe('2026-07-30T02:41:55Z')
    expect(a.pii_tokenized).toBe(true)
  })

  it('carries the rule/shap/graph reason codes (incl. ring RNG-12)', async () => {
    const a = await apiClient.getAlert('alr_3d7e22')
    const codes = a.reason_codes
    expect(
      codes.some((r) => r.source === 'rule' && r.code === 'NEW_BENEFICIARY_THEN_HIGHVALUE'),
    ).toBe(true)
    expect(codes.some((r) => r.source === 'rule' && r.code === 'OFF_HOURS_ACTIVITY')).toBe(true)
    expect(
      codes.some(
        (r) =>
          r.source === 'shap' &&
          r.feature === 'new_beneficiary_to_payment_latency_min' &&
          r.contribution === 0.31,
      ),
    ).toBe(true)
    expect(codes.some((r) => r.source === 'graph' && r.detail.includes('RNG-12'))).toBe(true)
  })

  it('appears in the ranked queue', async () => {
    const page = await apiClient.listAlerts({})
    expect(page.items.some((a) => a.alert_id === 'alr_3d7e22')).toBe(true)
  })
})

describe('Part 24.5(a) — sample event evt_8f2a1c90 (via timeline)', () => {
  it('renders the L0 actor/action/object/context groups', async () => {
    const tl = await apiClient.getEntityTimeline('EMP-7f3a')
    const ev = tl.events.find((e) => e.event_id === 'evt_8f2a1c90')
    expect(ev).toBeDefined()
    expect(ev?.action.verb).toBe('create_beneficiary')
    expect(ev?.action.maker_checker).toBe('maker')
    expect(ev?.action.channel).toBe('cbs')
    expect(ev?.context.layer).toBe('application')
    expect(ev?.context.is_off_hours).toBe(true)
    expect(ev?.actor.employee_id).toBe('EMP-7f3a')
  })
})

describe('explanations + narrative (Part 11 / Part 25)', () => {
  it('returns SHAP + rule provenance + LAXCAT attention + graph evidence', async () => {
    const exp = await apiClient.getExplanation('alr_3d7e22')
    expect(exp.shap.length).toBeGreaterThan(0)
    expect(exp.rules.some((r) => r.code === 'NEW_BENEFICIARY_THEN_HIGHVALUE')).toBe(true)
    expect(exp.attention[0]?.model).toBe('LAXCAT')
    expect(exp.graph?.ring_id).toBe('RNG-12')
    expect(exp.graph?.explainer_model).toBe('GNNExplainer')
    // structured subgraph is drawable (inline mini-graph): >=2 nodes and edges reference them
    expect(exp.graph?.nodes.length ?? 0).toBeGreaterThanOrEqual(2)
    const ids = new Set(exp.graph?.nodes.map((n) => n.id))
    for (const e of exp.graph?.edges ?? []) {
      expect(ids.has(e.source) && ids.has(e.target)).toBe(true)
    }
  })

  it('exposes a per-layer score timeline (deferred polish)', async () => {
    const ls = await apiClient.getLayerScores('EMP-7f3a')
    expect(ls.threshold_score).toBe(70)
    const layers = ls.series.map((s) => s.layer)
    expect(layers).toContain('L3_gbdt')
    expect(layers).toContain('L6_fusion')
    for (const s of ls.series) {
      expect(s.points.length).toBeGreaterThan(1)
      for (const p of s.points) {
        expect(p.score).toBeGreaterThanOrEqual(0)
        expect(p.score).toBeLessThanOrEqual(100)
      }
    }
  })

  it('exposes fraud-typology prevalence + confirmed-rate (Phase 5)', async () => {
    const a = await apiClient.getTypologyAnalytics()
    expect(a.typologies.length).toBeGreaterThanOrEqual(10)
    const counts = a.typologies.map((t) => t.alerts)
    expect(counts).toEqual([...counts].sort((x, y) => y - x)) // ranked by prevalence
    expect(a.totals.alerts).toBe(a.typologies.reduce((s, t) => s + t.alerts, 0))
    for (const t of a.typologies) {
      expect(t.open).toBe(t.alerts - t.confirmed - t.false_positive)
      expect(t.confirmed_rate).toBeGreaterThanOrEqual(0)
      expect(t.confirmed_rate).toBeLessThanOrEqual(1)
      expect(t.layers.length).toBeGreaterThan(0)
    }
  })

  it('exposes the sub-threshold detection funnel + near-miss watchlist (Phase 4)', async () => {
    const st = await apiClient.getSubThreshold()
    expect(st.emit_threshold).toBe(70)
    expect(st.sub_threshold).toBe(st.bands.reduce((s, b) => s + b.count, 0))
    expect(st.total_scored).toBe(st.alerted + st.sub_threshold)
    expect(st.sub_threshold).toBeGreaterThan(st.alerted) // the silent majority
    expect(st.watchlist.length).toBeGreaterThan(0)
    for (const w of st.watchlist) expect(w.score).toBeGreaterThanOrEqual(40)
  })

  it('carries per-layer model lineage + governance posture (Phase 6)', async () => {
    const exp = await apiClient.getExplanation('alr_3d7e22')
    const lineage = exp.model_lineage
    expect(lineage && lineage.length).toBeTruthy()
    const layers = lineage!.map((l) => l.layer)
    expect(layers).toContain('L6_fusion') // fusion is always in the lineage
    expect(layers).toContain('L3_gbdt') // the worked burst contributes L3
    for (const l of lineage!) {
      expect(l.model_id && l.version && l.stage).toBeTruthy()
      expect(typeof l.signed).toBe('boolean')
    }
  })

  it('carries LAXCAT variable×temporal attention + SHAP peer percentiles (Phase 2)', async () => {
    const exp = await apiClient.getExplanation('alr_3d7e22')
    // every attention step now carries the variable axis (the heatmap rows)
    const step = exp.attention[0]?.steps[0]
    expect(step?.variables?.length).toBeGreaterThan(0)
    expect(step?.variables?.some((v) => v.name === 'off_hours')).toBe(true)
    // every SHAP feature carries a peer percentile (the "vs baseline" depth)
    expect(exp.shap.every((f) => typeof f.percentile === 'number')).toBe(true)
  })

  it('carries the full 5-layer L6 fusion decomposition (Phase 1 — Detection Transparency)', async () => {
    const exp = await apiClient.getExplanation('alr_3d7e22')
    const f = exp.fusion
    expect(f).toBeDefined()
    // all five detection layers are decomposed (incl. the L1 rule floor + L4 sequence)
    expect(f!.components.map((c) => c.layer)).toEqual([
      'L1_rule',
      'L2_unsupervised',
      'L3_gbdt',
      'L4_sequence',
      'L5_graph',
    ])
    expect(typeof f!.agreement).toBe('number')
    expect(f!.calibrated_score).toBe(Math.round(f!.fused * 100))
    // contribution = weight × proba for every layer that ran (auditable arithmetic)
    for (const c of f!.components) {
      if (c.proba != null) {
        expect(Math.abs((c.contribution ?? 0) - c.weight * c.proba)).toBeLessThan(1e-3)
      }
    }
    // worked burst is the canonical "rescued by graph fusion" story
    expect(f!.rescued).toBe(true)
    expect(f!.decisive_layer).toBe('L5_graph')
  })

  it('TEE-attested narrative for the worked burst', async () => {
    const memo = await apiClient.getNarrative('alr_3d7e22')
    expect(memo.provider).toBe('near_ai')
    expect(memo.tee_attested).toBe(true)
    expect(memo.attestation_id).toBeTruthy()
    expect(memo.narrative.length).toBeGreaterThan(20)
  })

  it('degrades gracefully to a deterministic template (tee_attested=false)', async () => {
    const memo = await apiClient.getNarrative('alr_4d88')
    expect(memo.provider).toBe('template')
    expect(memo.tee_attested).toBe(false)
    expect(memo.attestation_id).toBeNull()
    expect(memo.narrative.length).toBeGreaterThan(0) // never empty — UI never breaks
  })
})

describe('Part 24.5(c) — disposition → label + audit', () => {
  it('writes a label, queues retraining, and returns an audit id', async () => {
    const res = await apiClient.dispositionAlert('alr_1e90', {
      outcome: 'fraud',
      notes: 'Confirmed shell beneficiary; maker-checker collusion.',
      evidence_ids: ['evt_8f2a1c90'],
    })
    expect(res.alert_id).toBe('alr_1e90')
    expect(res.status).toBe('confirmed_fraud')
    expect(res.label_written).toBe(true)
    expect(res.feedback_queued_for_retraining).toBe(true)
    expect(res.audit_id).toMatch(/^aud_/)
  })

  it('block-request is a request routed to a Lead — never an auto-block', async () => {
    const res = await apiClient.blockRequest('alr_8c23', { reason: 'limit breach' })
    expect(res.status).toBe('pending_lead_approval')
    expect(res.routed_to_role).toBe('team_lead')
    expect(res.audit_id).toMatch(/^aud_/)
  })
})
