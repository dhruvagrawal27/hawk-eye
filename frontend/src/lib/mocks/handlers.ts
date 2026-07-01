/**
 * MSW request handlers — bind every `apiClient` route to the Part 24.5 fixtures. Mutations mutate
 * the in-memory fixtures so a disposition/assign/unmask is reflected for the rest of the session.
 * Fallback builders guarantee every entity/alert renders even without a hand-authored fixture, so
 * the console never shows an empty panel during a demo.
 */
import { http, HttpResponse } from 'msw'
import { env } from '../env'
import type {
  Alert,
  AssignResponse,
  AttestationDetail,
  AuditEvent,
  BlockRequestResponse,
  DispositionRequest,
  DispositionResponse,
  ExplanationResponse,
  FusionBreakdown,
  GraphResponse,
  LayerScoresResponse,
  PeerComparisonResponse,
  RiskIndex,
  ActionHold,
  ActionPolicy,
  ScoreHistoryResponse,
  TimelineResponse,
  AlertStatus,
  CreateUserBody,
} from '../types'
import {
  ALERTS,
  AUDIT,
  CASES,
  DRIFT,
  ENTITIES,
  EWS_COVERAGE,
  EXPLANATIONS,
  GRAPHS,
  HEALTH,
  READYZ,
  KRIS,
  METRICS_TEXT,
  MODELS,
  MODEL_QUALITY,
  PEERS,
  RULES,
  SUB_THRESHOLD,
  TIMELINES,
  TYPOLOGY_ANALYTICS,
  USERS,
  findAlert,
  findCase,
  narrativeFor,
  reportFor,
  unmaskValue,
} from './fixtures'

const api = (path: string): string => `${env.apiBaseUrl.replace(/\/$/, '')}${path}`

const TOKEN = {
  access_token: 'mock.jwt.analyst',
  token_type: 'Bearer' as const,
  expires_in: 900,
  refresh_token: 'mock.refresh',
}

/* ── fallback builders ──────────────────────────────────────────────────── */

/** Decision threshold on the 0–1 fusion scale — mirrors the backend (EMIT_THRESHOLD / 100). */
const FUSION_THRESHOLD = 0.7

/** Meta-learner coefficients + presentation chrome per layer — mirror of backend LAYER_META_WEIGHTS. */
const FUSION_LAYER_META: {
  layer: string
  label: string
  sublabel: string
  weight: number
}[] = [
  { layer: 'L1_rule', label: 'Rules / BRE', sublabel: 'L1 · deterministic', weight: 1.7 },
  { layer: 'L2_unsupervised', label: 'Anomaly', sublabel: 'L2 · unsupervised', weight: 1.2 },
  {
    layer: 'L3_gbdt',
    label: 'Gradient-boosted trees',
    sublabel: 'L3 · supervised tabular',
    weight: 2.4,
  },
  { layer: 'L4_sequence', label: 'Sequence', sublabel: 'L4 · attention', weight: 1.0 },
  { layer: 'L5_graph', label: 'Graph / collusion', sublabel: 'L5 · GNN', weight: 1.2 },
]

/**
 * Synthesize the full 5-layer L6 fusion breakdown for an alert — the same shape the backend now
 * serves from `fusion.build_breakdown`. The fused probability tracks the alert's calibrated 0–100
 * risk_score; per-layer probabilities are derived from which layers contributed, with GBDT modelled
 * *just under* threshold when graph is present so the canonical "rescued by graph fusion" story
 * holds on the worked example. Contribution = weight × proba; agreement = 1 − 2·std(probas).
 */
function buildFusion(alert: Alert | undefined): FusionBreakdown {
  const fused = alert ? Math.min(0.99, Math.max(0, alert.risk_score / 100)) : 0.5
  const fired = new Set(
    (alert?.contributing_layers ?? []).map((l) =>
      String(l) === 'L1_rules' ? 'L1_rule' : String(l),
    ),
  )
  const hasGraph = fired.has('L5_graph')

  const probaFor = (layer: string): number | null => {
    if (!fired.has(layer)) return null
    switch (layer) {
      case 'L1_rule':
        return 0.45 // rules fired but soft, so graph can be decisive in the rescue story
      case 'L2_unsupervised':
        return Math.min(0.9, 0.3 + fused * 0.4)
      case 'L3_gbdt':
        return hasGraph ? Number((FUSION_THRESHOLD * 0.85).toFixed(4)) : Math.min(0.95, fused)
      case 'L4_sequence':
        return Math.min(0.95, fused * 0.7)
      case 'L5_graph':
        return Math.min(0.97, Math.max(fused, 0.6))
      default:
        return null
    }
  }

  const components = FUSION_LAYER_META.map((m) => {
    const proba = probaFor(m.layer)
    return {
      layer: m.layer,
      label: m.label,
      sublabel: m.sublabel,
      proba: proba != null ? Number(proba.toFixed(4)) : null,
      weight: m.weight,
      contribution: proba != null ? Number((m.weight * proba).toFixed(4)) : 0,
    }
  })

  const firedComps = components.filter((c) => c.proba != null)
  const probs = firedComps.map((c) => c.proba as number)
  const mean = probs.reduce((s, p) => s + p, 0) / (probs.length || 1)
  const variance = probs.reduce((s, p) => s + (p - mean) ** 2, 0) / (probs.length || 1)
  const agreement = Number(Math.max(0, 1 - Math.min(1, Math.sqrt(variance) * 2)).toFixed(4))

  const gbdt = components.find((c) => c.layer === 'L3_gbdt')
  const nonGbdt = firedComps.filter((c) => c.layer !== 'L3_gbdt')
  const rescued =
    !!gbdt &&
    gbdt.proba != null &&
    gbdt.proba < FUSION_THRESHOLD &&
    fused >= FUSION_THRESHOLD &&
    nonGbdt.length > 0
  const pool = rescued && nonGbdt.length ? nonGbdt : firedComps
  const decisive = pool.reduce<(typeof components)[number] | null>(
    (a, b) => (a == null || b.contribution > a.contribution ? b : a),
    null,
  )

  return {
    fused,
    threshold: FUSION_THRESHOLD,
    calibrated_score: Math.round(fused * 100),
    agreement,
    confidence: alert?.confidence ?? Number((0.5 * agreement + 0.5 * fused).toFixed(2)),
    hard_hit: alert?.severity === 'high' && fired.has('L1_rule'),
    rescued,
    decisive_layer: decisive?.layer ?? null,
    meta_version: 'l6_meta@stub-2026.06.30',
    components,
  }
}

/**
 * Synthesize LAXCAT per-variable attention for a step (the *variable* axis of the variable×temporal
 * map). Deterministic from the step's verb / off-hours / temporal weight so the heatmap is stable.
 */
function stepVariables(step: {
  verb?: string
  label?: string
  weight: number
  is_off_hours?: boolean
}): { name: string; weight: number }[] {
  const verb = String(step.verb ?? step.label ?? '')
  const amountVerb = /payment|beneficiary|transfer|trade|invoice|disburse|export/i.test(verb)
  const clamp = (n: number) => Math.max(0, Math.min(1, Number(n.toFixed(3))))
  return [
    { name: 'verb', weight: clamp(0.45 + step.weight * 0.5) },
    { name: 'log_amount', weight: clamp((amountVerb ? 0.6 : 0.15) * (0.6 + step.weight * 0.4)) },
    { name: 'off_hours', weight: clamp(step.is_off_hours ? 0.5 + step.weight * 0.45 : 0.08) },
    { name: 'velocity_1h', weight: clamp(0.2 + step.weight * 0.55) },
  ]
}

function enrichAttention(
  sessions: ExplanationResponse['attention'],
): ExplanationResponse['attention'] {
  return sessions.map((s) => ({
    ...s,
    steps: s.steps.map((st) => ({ ...st, variables: st.variables ?? stepVariables(st) })),
  }))
}

/** Add an honest peer percentile to each SHAP feature when the fixture didn't specify one. */
function enrichShap(shap: ExplanationResponse['shap']): ExplanationResponse['shap'] {
  return shap.map((f) => ({
    ...f,
    percentile:
      f.percentile ?? Math.max(0.01, Math.min(0.99, Number((0.5 + f.contribution).toFixed(2)))),
  }))
}

/** Per-layer model lineage — mirror of the backend registry (which model fired each layer + posture). */
const LINEAGE_REGISTRY: Record<
  string,
  { model_id: string; version: string; risk_tier: string; metrics: Record<string, number> }
> = {
  L1_rule: { model_id: 'rules_engine', version: '1.x', risk_tier: 'deterministic', metrics: {} },
  L2_unsupervised: {
    model_id: 'l2_isoforest',
    version: 'stub-2026.06.30',
    risk_tier: 'tier-2-high',
    metrics: { pr_auc: 0.71 },
  },
  L3_gbdt: {
    model_id: 'l3_lightgbm',
    version: 'stub-2026.06.30',
    risk_tier: 'tier-1-critical',
    metrics: { pr_auc: 0.86, precision_at_k: 0.62 },
  },
  L4_sequence: {
    model_id: 'l4_usad',
    version: 'stub-2026.06.30',
    risk_tier: 'tier-3-moderate',
    metrics: { vus_pr: 0.64 },
  },
  L6_fusion: {
    model_id: 'l6_meta',
    version: 'l6_meta@stub-2026.06.30',
    risk_tier: 'tier-1-critical',
    metrics: { calibration_error: 0.03 },
  },
}

function buildLineage(alert: Alert | undefined): ExplanationResponse['model_lineage'] {
  const fired = new Set(
    (alert?.contributing_layers ?? []).map((l) =>
      String(l) === 'L1_rules' ? 'L1_rule' : String(l),
    ),
  )
  const layers = ['L1_rule', 'L2_unsupervised', 'L3_gbdt', 'L4_sequence', 'L6_fusion'].filter(
    (l) => l === 'L6_fusion' || fired.has(l),
  )
  return layers.map((layer) => {
    const r = LINEAGE_REGISTRY[layer]
    return {
      layer,
      model_id: r.model_id,
      version: r.version,
      stage: 'Production',
      risk_tier: r.risk_tier,
      signed: true,
      approving_reviewer: layer === 'L1_rule' ? 'dgm_compliance' : 'EMP-me01',
      metrics: r.metrics,
    }
  })
}

function buildExplanation(alertId: string): ExplanationResponse {
  const a = findAlert(alertId)
  const fusion = buildFusion(a)
  if (EXPLANATIONS[alertId]) {
    const base = EXPLANATIONS[alertId]
    return {
      ...base,
      shap: enrichShap(base.shap),
      attention: enrichAttention(base.attention),
      fusion,
      model_lineage: base.model_lineage ?? buildLineage(a),
    }
  }
  const reasons = a?.reason_codes ?? []
  return {
    alert_id: alertId,
    shap: enrichShap(
      reasons
        .filter((r): r is Extract<typeof r, { source: 'shap' }> => r.source === 'shap')
        .map((r) => ({
          feature: r.feature,
          contribution: r.contribution,
          direction: (r.contribution >= 0 ? 'increases_risk' : 'decreases_risk') as
            'increases_risk' | 'decreases_risk',
        })),
    ),
    rules: reasons
      .filter((r): r is Extract<typeof r, { source: 'rule' }> => r.source === 'rule')
      .map((r) => ({ code: r.code, detail: r.detail, severity: a?.severity, layer: 'L1_rules' })),
    attention: [],
    graph: reasons.find((r) => r.source === 'graph')
      ? {
          summary: (reasons.find((r) => r.source === 'graph') as { detail: string }).detail,
          nodes: [],
          edges: [],
        }
      : undefined,
    fusion,
    model_lineage: buildLineage(a),
  }
}

/**
 * Synthesize a 0–100 fused-risk-score history for an entity: a deterministic, gently-rising series
 * that culminates at the entity's current risk_score, with a couple of labelled inflection points so
 * the chart tells a story (baseline → off-hours burst → current). Pure function of the entity id so
 * it is stable across renders / contract tests.
 */
function buildRiskIndex(entityId: string): RiskIndex {
  const e = ENTITIES[entityId]
  const base = (e?.risk_score ?? 50) / 100
  const hr = Math.min(1, base * 0.75 + 0.1)
  const access = Math.min(1, base * 0.6 + 0.05)
  const anomaly = Math.min(1, base * 0.95)
  const composite = Math.round((0.3 * hr + 0.35 * access + 0.35 * anomaly) * 100)
  return {
    employee_id: entityId,
    composite,
    hr_score: Number(hr.toFixed(3)),
    access_score: Number(access.toFixed(3)),
    anomaly_score: Number(anomaly.toFixed(3)),
    components: [
      {
        name: 'offhours_score',
        group: 'anomaly',
        value: Number(anomaly.toFixed(3)),
        detail: 'off-hours activity',
      },
      {
        name: 'role_change_recency',
        group: 'hr',
        value: Number(hr.toFixed(3)),
        detail: 'recent role change',
      },
      {
        name: 'standing_privilege',
        group: 'access',
        value: Number(access.toFixed(3)),
        detail: 'unexercised held entitlements',
      },
    ],
    top_drivers: ['offhours_score', 'role_change_recency', 'standing_privilege'],
    updated_ts: '2026-06-30T06:00:00Z',
    calibrated: false,
  }
}

/* L6.5 console fixtures (M3.4). Mutable so a four-eyes decision persists for the session. */
const ACTION_HOLDS: ActionHold[] = [
  {
    hold_id: 'hold_9a1c22',
    request_id: 'req_7f3a01',
    subject: 'EMP-3c55',
    verb: 'self_grant',
    status: 'pending_review',
    severity: 'high',
    reason_codes: [
      { source: 'policy', code: 'SELF_GRANT_HOLD', detail: 'Entitlement self-grant (hard-gate)' },
    ],
    proportionality: 'reversible staff action held pending second-approver review',
    explanation: 'DBA attempted to self-grant approve_payment entitlement in a privileged session',
    dpia_binding: true,
    decider: null,
    justification: null,
    outcome: null,
    ts: '2026-06-30T02:41:00Z',
  },
  {
    hold_id: 'hold_4d8811',
    request_id: 'req_2b1409',
    subject: 'EMP-7f3a',
    verb: 'bulk_export',
    status: 'pending_review',
    severity: 'high',
    reason_codes: [
      {
        source: 'policy',
        code: 'BULK_EXPORT_HOLD',
        detail: 'Bulk export from a privileged session (hard-gate)',
      },
    ],
    proportionality: 'reversible staff action held pending second-approver review',
    explanation: 'Mass SELECT/export of customer_pii detected in the PAM session (content-parsed)',
    dpia_binding: true,
    decider: null,
    justification: null,
    outcome: null,
    ts: '2026-06-30T02:55:00Z',
  },
]

const ACTION_POLICIES: ActionPolicy[] = [
  {
    code: 'SELF_GRANT_HOLD',
    name: 'Entitlement self-grant',
    gate: 'hard',
    severity: 'high',
    enabled: true,
    verbs: ['grant_entitlement', 'self_grant'],
  },
  {
    code: 'MAKER_CHECKER_SAME_ACTOR_HOLD',
    name: 'Maker+checker by the same actor',
    gate: 'hard',
    severity: 'high',
    enabled: true,
    verbs: [],
  },
  {
    code: 'BULK_EXPORT_HOLD',
    name: 'Bulk export from a privileged session',
    gate: 'hard',
    severity: 'high',
    enabled: true,
    verbs: ['export', 'bulk_export'],
  },
  {
    code: 'SWIFT_SEND_STEP_UP',
    name: 'SWIFT / SO message send',
    gate: 'soft',
    severity: 'high',
    enabled: true,
    verbs: ['swift_send', 'so_send'],
  },
  {
    code: 'DB_WRITE_STEP_UP',
    name: 'Direct DB write',
    gate: 'soft',
    severity: 'medium',
    enabled: true,
    verbs: ['db_write', 'direct_write'],
  },
]

function buildScoreHistory(entityId: string): ScoreHistoryResponse {
  const e = ENTITIES[entityId]
  const current = e?.risk_score ?? 50
  // Walk back 8 weekly points from the current score, easing down toward a calm baseline.
  const POINTS = 8
  const baseline = Math.max(8, Math.round(current * 0.25))
  const start = new Date('2026-06-30T00:00:00Z').getTime()
  const weekMs = 7 * 86_400_000

  const points = Array.from({ length: POINTS }).map((_, i) => {
    const t = i / (POINTS - 1) // 0..1
    // Ease-in so the climb steepens toward the alert; deterministic jitter keeps it organic.
    const eased = t * t
    const jitter = ((entityId.charCodeAt(entityId.length - 1) + i * 7) % 5) - 2
    const score = Math.round(baseline + (current - baseline) * eased + (i === 0 ? 0 : jitter))
    const ts = new Date(start - (POINTS - 1 - i) * weekMs).toISOString()
    let note: string | undefined
    if (i === 0) note = 'baseline within peer range'
    else if (i === POINTS - 2) note = 'off-hours activity burst'
    else if (i === POINTS - 1) note = 'current — alert raised'
    return { ts, score: Math.min(100, Math.max(0, score)), note }
  })

  return {
    entity_id: entityId,
    points,
    threshold_score: Math.round(FUSION_THRESHOLD * 100),
  }
}

/** Per-layer score timeline — mirror of the backend synthesis (one series per detection layer). */
function buildLayerScores(entityId: string): LayerScoresResponse {
  const fused = ENTITIES[entityId]?.risk_score ?? 50
  const start = new Date('2026-06-30T00:00:00Z').getTime()
  const weekMs = 7 * 86_400_000
  const shapes: {
    layer: string
    label: string
    frac: number
    curve: 'early' | 'late' | 'steady'
  }[] = [
    { layer: 'L2_unsupervised', label: 'Anomaly', frac: 0.62, curve: 'steady' },
    { layer: 'L3_gbdt', label: 'GBDT', frac: 0.9, curve: 'early' },
    { layer: 'L4_sequence', label: 'Sequence', frac: 0.5, curve: 'steady' },
    { layer: 'L5_graph', label: 'Graph', frac: 0.8, curve: 'late' },
    { layer: 'L6_fusion', label: 'Fused L6', frac: 1.0, curve: 'early' },
  ]
  const wobble = (layer: string, i: number) => ((layer.charCodeAt(0) + i * 13) % 7) - 3
  const series = shapes.map((s) => {
    const target = fused * s.frac
    const base = Math.max(4, target * 0.25)
    const points = Array.from({ length: 8 }).map((_, i) => {
      const t = i / 7
      const shape = s.curve === 'late' ? t ** 3 : s.curve === 'early' ? t ** 0.6 : t * t
      const score = Math.round(base + (target - base) * shape + wobble(s.layer, i))
      const ts = new Date(start - (7 - i) * weekMs).toISOString()
      return { ts, score: Math.min(100, Math.max(0, score)) }
    })
    return { layer: s.layer, label: s.label, model_version: 'stub-2026.06.30', points }
  })
  return { entity_id: entityId, threshold_score: 70, series }
}

/**
 * Synthesize per-request TEE attestation detail for a narrative. Mirrors the narrative fixture's
 * attestation state: attested narratives return the full cryptographic trail; non-attested ones
 * honestly report `tee_attested: false` with no signing material.
 */
function buildAttestation(alertId: string): AttestationDetail {
  const memo = narrativeFor(alertId)
  if (!memo.tee_attested) {
    return {
      alert_id: alertId,
      tee_attested: false,
      provider: memo.provider,
      model: memo.model,
    }
  }
  return {
    alert_id: alertId,
    tee_attested: true,
    provider: memo.provider,
    gateway: 'near-ai-confidential-1',
    model: memo.model,
    signing_address: '0x9b1c7f3a4d04e2a1c905f2c918f2a1b02d77e1a0',
    signing_algo: 'secp256k1',
    intel_quote_sha256: 'sha256:5f2c91a3d04e8f2a1b02d77e1a09b1c7f3a4d04e2a1c905f2c918f2a1b02',
    attestation_id: memo.attestation_id ?? 'att_tdx_h200_5f2c91',
    verified_ts: memo.ts,
    extra: [{ label: 'Enclave', value: 'Intel TDX · H200' }],
  }
}

function buildTimeline(entityId: string): TimelineResponse {
  if (TIMELINES[entityId]) return TIMELINES[entityId]
  const e = ENTITIES[entityId]
  const base = e?.role ?? 'employee'
  return {
    entity_id: entityId,
    events: ['login', `${base}_action`, 'query_table', 'logout'].map((verb, i) => ({
      event_id: `evt_gen_${entityId}_${i}`,
      ts: `2026-06-2${8 + (i % 2)}T0${i + 1}:00:00Z`,
      actor: {
        employee_id: entityId,
        role: e?.role ?? 'employee',
        dept: e?.dept ?? 'unknown',
        branch: e?.branch ?? 'BR-000',
        tenure_days: e?.tenure_days ?? 1000,
        peer_group: e?.peer_group ?? 'PG-unknown',
        privileged_flag: e?.privileged_flag ?? false,
        leaver_flag: e?.leaver_flag ?? false,
      },
      action: { verb, channel: i % 2 ? 'iam' : 'cbs', maker_checker: null },
      object: { beneficiary_id: null, account_id: null, amount: null, currency: 'INR' },
      context: {
        src_ip: '10.20.4.31',
        device: 'WS-000',
        geo: 'Mumbai',
        session_id: 'sess_gen',
        layer: i % 2 ? 'identity' : 'application',
        is_off_hours: i === 1,
      },
    })),
  }
}

function buildGraph(entityId: string, depth = 1): GraphResponse {
  const base: GraphResponse = GRAPHS[entityId] ?? {
    entity_id: entityId,
    nodes: [
      {
        id: entityId,
        type: 'employee',
        label: entityId,
        risk: ENTITIES[entityId]?.risk_score ?? 50,
        is_focus: true,
        tokenized: true,
      },
      {
        id: `BEN-${entityId.slice(-4)}`,
        type: 'beneficiary',
        label: `BEN-${entityId.slice(-4)}`,
        tokenized: true,
      },
      {
        id: `ACCT-${entityId.slice(-4)}`,
        type: 'account',
        label: `ACCT-${entityId.slice(-4)}`,
        tokenized: true,
      },
    ],
    edges: [
      { id: 'g1', source: entityId, target: `BEN-${entityId.slice(-4)}`, type: 'beneficiary' },
      {
        id: 'g2',
        source: `BEN-${entityId.slice(-4)}`,
        target: `ACCT-${entityId.slice(-4)}`,
        type: 'beneficiary',
      },
    ],
  }

  // Depth-expand: each extra hop attaches a fresh ring of synthetic neighbours to the existing
  // leaf nodes, widening the subgraph the way a real N-hop traversal would. depth=1 is the base.
  const hops = Math.max(1, Math.min(3, Math.round(depth)))
  if (hops === 1) return base

  const nodes = [...base.nodes]
  const edges = [...base.edges]
  const seen = new Set(nodes.map((n) => n.id))
  const neighbourTypes = ['account', 'device', 'ip', 'customer'] as const

  let frontier = nodes.filter((n) => n.id !== entityId).map((n) => n.id)
  for (let hop = 2; hop <= hops; hop += 1) {
    const next: string[] = []
    frontier.forEach((srcId, idx) => {
      const type = neighbourTypes[(hop + idx) % neighbourTypes.length]
      const nid = `${type.toUpperCase().slice(0, 4)}-${entityId.slice(-4)}-h${hop}-${idx}`
      if (seen.has(nid)) return
      seen.add(nid)
      next.push(nid)
      nodes.push({
        id: nid,
        type,
        label: nid,
        risk: Math.max(20, 70 - hop * 12 - idx * 3),
        tokenized: type === 'customer',
      })
      edges.push({
        id: `g_h${hop}_${idx}`,
        source: srcId,
        target: nid,
        type:
          type === 'account' ? 'transaction' : `shared_${type === 'customer' ? 'address' : type}`,
      })
    })
    frontier = next
  }

  return { ...base, nodes, edges }
}

/**
 * Synthesize a global top-risk overview subgraph from the existing ENTITIES pool: the riskiest
 * employees (risk ≥ minScore) plus the shared systems/accounts they touch. Reuses GraphResponse so
 * one canvas renders it; `entity_id` is a synthetic overview marker (no single focus). Swap to the
 * real `GET /graph` route later by deleting this builder.
 */
function buildGraphOverview(minScore: number, limit: number): GraphResponse {
  const seeds = Object.values(ENTITIES)
    .filter((e) => e.risk_score >= minScore)
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, limit)

  const nodes: GraphResponse['nodes'] = []
  const edges: GraphResponse['edges'] = []
  // A small shared-systems backbone every high-risk employee can attach to.
  const systems = [
    { id: 'SYS-CBS', label: 'Core Banking (CBS)', risk: 0 },
    { id: 'SYS-SWIFT', label: 'SWIFT Gateway', risk: 0 },
    { id: 'SYS-IAM', label: 'Identity (IAM)', risk: 0 },
  ]
  for (const s of systems) {
    nodes.push({ id: s.id, type: 'system', label: s.label, risk: s.risk })
  }

  seeds.forEach((e, i) => {
    nodes.push({
      id: e.entity_id,
      type: 'employee',
      label: e.entity_id,
      risk: e.risk_score,
      tokenized: true,
    })
    // Wire each employee to a couple of shared systems (round-robin) — that overlap is the signal.
    const a = systems[i % systems.length]
    const b = systems[(i + 1) % systems.length]
    edges.push({
      id: `ov_${e.entity_id}_a`,
      source: e.entity_id,
      target: a.id,
      type: 'shared_device',
    })
    edges.push({
      id: `ov_${e.entity_id}_b`,
      source: e.entity_id,
      target: b.id,
      type: 'transaction',
    })
    // The two riskiest seeds share a maker-checker collusion edge to seed the find-path demo.
    if (i > 0 && i < 2) {
      edges.push({
        id: `ov_mc_${i}`,
        source: seeds[i - 1].entity_id,
        target: e.entity_id,
        type: 'maker_checker',
        label: 'maker→checker',
        collusion: true,
        weight: 10,
      })
    }
  })

  return { entity_id: 'OVERVIEW', nodes, edges }
}

function buildPeers(entityId: string): PeerComparisonResponse {
  if (PEERS[entityId]) return PEERS[entityId]
  const e = ENTITIES[entityId]
  return {
    entity_id: entityId,
    peer_group: e?.peer_group ?? 'PG-unknown',
    peer_count: 20,
    dimensions: [
      {
        key: 'off_hours_activity_rate_30d',
        label: 'Off-hours activity rate (30d)',
        unit: '%',
        actor_value: 28,
        z_score: 1.8,
        flagged: true,
        direction: 'higher_is_riskier',
        peer_distribution: {
          min: 0,
          p25: 3,
          median: 7,
          p75: 12,
          max: 22,
          mean: 8,
          stddev: 4,
          samples: [2, 4, 6, 7, 9, 12, 18, 28],
        },
      },
    ],
  }
}

/* ── mutation helpers ───────────────────────────────────────────────────── */

const outcomeToStatus: Record<DispositionRequest['outcome'], AlertStatus> = {
  fraud: 'confirmed_fraud',
  false_positive: 'false_positive',
  inconclusive: 'inconclusive',
}

let auditSeq = 1000
function nextAuditId(): string {
  auditSeq += 1
  return `aud_${auditSeq.toString(16)}`
}

function recordAudit(ev: Omit<AuditEvent, 'audit_id' | 'ts'>): string {
  const audit_id = nextAuditId()
  AUDIT.unshift({ audit_id, ts: new Date().toISOString(), ...ev })
  return audit_id
}

/* ── handlers ───────────────────────────────────────────────────────────── */

export const handlers = [
  // Auth
  http.post(api('/auth/login'), () => HttpResponse.json(TOKEN)),
  http.post(api('/auth/refresh'), () => HttpResponse.json(TOKEN)),

  // Alerts / triage
  http.get(api('/alerts'), ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status') as AlertStatus | null
    const riskGte = url.searchParams.get('risk_gte')
    const assignee = url.searchParams.get('assignee')
    const type = url.searchParams.get('type')
    let items: Alert[] = [...ALERTS]
    if (status) items = items.filter((a) => a.status === status)
    if (riskGte) items = items.filter((a) => a.risk_score >= Number(riskGte))
    if (assignee) items = items.filter((a) => a.assignee === assignee)
    if (type) items = items.filter((a) => a.alert_type === type)
    return HttpResponse.json({ items, total: items.length })
  }),
  // Portfolio counts (must precede /alerts/:id). Demo values at real-bank scale (hundreds).
  http.get(api('/alerts/stats'), () =>
    HttpResponse.json({
      total: 454,
      open: 388,
      high_critical: 200,
      sla_at_risk: 122,
      confirmed_fraud: 1,
      open_exposure_inr: 742_000_000,
    }),
  ),
  http.get(api('/alerts/:id'), ({ params }) => {
    const a = findAlert(String(params.id))
    return a ? HttpResponse.json(a) : new HttpResponse('alert not found', { status: 404 })
  }),
  http.post(api('/alerts/:id/assign'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as { assignee?: string }
    const a = findAlert(id)
    if (!a) return new HttpResponse('alert not found', { status: 404 })
    a.assignee = body.assignee ?? 'rm.demo'
    if (a.status === 'open') a.status = 'assigned'
    const audit_id = recordAudit({
      actor: a.assignee,
      actor_role: 'relationship_manager',
      action: 'assign',
      alert_id: id,
      entity_id: a.entity_id,
      outcome: 'claimed',
    })
    const res: AssignResponse = { alert_id: id, assignee: a.assignee, status: a.status, audit_id }
    return HttpResponse.json(res)
  }),
  http.post(api('/alerts/:id/disposition'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json()) as DispositionRequest
    const a = findAlert(id)
    if (!a) return new HttpResponse('alert not found', { status: 404 })
    a.status = outcomeToStatus[body.outcome]
    const audit_id = recordAudit({
      actor: 'rm.demo',
      actor_role: 'relationship_manager',
      action: 'disposition',
      alert_id: id,
      entity_id: a.entity_id,
      outcome: a.status,
      detail: body.notes,
    })
    const res: DispositionResponse = {
      alert_id: id,
      status: a.status,
      label_written: true,
      feedback_queued_for_retraining: true,
      audit_id,
    }
    return HttpResponse.json(res)
  }),
  http.post(api('/alerts/:id/block-request'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as { reason?: string }
    const a = findAlert(id)
    if (!a) return new HttpResponse('alert not found', { status: 404 })
    const audit_id = recordAudit({
      actor: 'rm.demo',
      actor_role: 'relationship_manager',
      action: 'block_request',
      alert_id: id,
      entity_id: a.entity_id,
      outcome: 'pending_lead_approval',
      detail: body.reason,
    })
    const res: BlockRequestResponse = {
      alert_id: id,
      request_id: `blk_${id.slice(-4)}`,
      status: 'pending_lead_approval',
      routed_to_role: 'team_lead',
      audit_id,
    }
    return HttpResponse.json(res)
  }),

  // Entity-360
  http.get(api('/entities/:id'), ({ params }) => {
    const e = ENTITIES[String(params.id)]
    if (!e) {
      const id = String(params.id)
      return HttpResponse.json({
        entity_id: id,
        employee_id: id,
        display_name: id,
        role: 'employee',
        dept: 'unknown',
        branch: 'BR-000',
        tenure_days: 1000,
        peer_group: 'PG-unknown',
        privileged_flag: false,
        leaver_flag: false,
        risk_score: 50,
        pii_tokenized: true,
      })
    }
    return HttpResponse.json(e)
  }),
  http.get(api('/entities/:id/timeline'), ({ params }) =>
    HttpResponse.json(buildTimeline(String(params.id))),
  ),
  http.get(api('/entities/:id/graph'), ({ params, request }) => {
    const depth = Number(new URL(request.url).searchParams.get('depth') ?? '1') || 1
    return HttpResponse.json(buildGraph(String(params.id), depth))
  }),

  // Global graph overview (Graph Explorer)
  http.get(api('/graph'), ({ request }) => {
    const url = new URL(request.url)
    const minScore = Number(url.searchParams.get('min_score') ?? '0') || 0
    const limit = Number(url.searchParams.get('limit') ?? '12') || 12
    return HttpResponse.json(buildGraphOverview(minScore, limit))
  }),
  http.get(api('/entities/:id/peers'), ({ params }) =>
    HttpResponse.json(buildPeers(String(params.id))),
  ),
  http.get(api('/entities/:id/layer-scores'), ({ params }) =>
    HttpResponse.json(buildLayerScores(String(params.id))),
  ),
  http.get(api('/entities/:id/score-history'), ({ params }) =>
    HttpResponse.json(buildScoreHistory(String(params.id))),
  ),
  http.get(api('/entities/:id/risk-index'), ({ params }) =>
    HttpResponse.json(buildRiskIndex(String(params.id))),
  ),

  /* ── L6.5 privileged-action interdiction console (M3.4) ─────────────────── */
  http.get(api('/action-gate/holds'), () =>
    HttpResponse.json({
      items: ACTION_HOLDS.filter((h) => h.status === 'pending_review'),
      count: ACTION_HOLDS.filter((h) => h.status === 'pending_review').length,
    }),
  ),
  http.post(api('/action-gate/holds/:id/decision'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as {
      decider?: string
      approve?: boolean
      justification?: string
    }
    const hold = ACTION_HOLDS.find((h) => h.hold_id === id)
    if (!hold) return new HttpResponse(null, { status: 404 })
    if (body.decider && body.decider === hold.subject)
      return HttpResponse.json(
        { detail: 'four-eyes: the subject cannot resolve their own hold' },
        { status: 403 },
      )
    hold.status = body.approve ? 'approved_via_four_eyes' : 'rejected'
    hold.outcome = body.approve ? 'permitted_for_human_initiated_execution' : 'denied_by_reviewer'
    hold.decider = body.decider ?? null
    hold.justification = body.justification ?? null
    return HttpResponse.json(hold)
  }),
  http.get(api('/action-gate/policies'), () => HttpResponse.json(ACTION_POLICIES)),
  http.post(api('/entities/:id/unmask'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as { alert_id?: string }
    recordAudit({
      actor: 'branch.demo',
      actor_role: 'branch_manager',
      action: 'unmask_pii',
      entity_id: id,
      alert_id: body.alert_id ?? null,
      outcome: 'success',
    })
    return HttpResponse.json(unmaskValue(id))
  }),

  // Explanation + narrative
  http.get(api('/explanations/:id'), ({ params }) =>
    HttpResponse.json(buildExplanation(String(params.id))),
  ),
  http.post(api('/narratives/:id'), ({ params }) =>
    HttpResponse.json(narrativeFor(String(params.id))),
  ),
  http.get(api('/narratives/:id/attestation'), ({ params }) =>
    HttpResponse.json(buildAttestation(String(params.id))),
  ),

  // Feedback
  http.post(api('/feedback'), async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { alert_id?: string }
    const audit_id = recordAudit({
      actor: 'rm.demo',
      actor_role: 'relationship_manager',
      action: 'feedback',
      alert_id: body.alert_id ?? null,
    })
    return HttpResponse.json({
      feedback_id: `fb_${Date.now().toString(16)}`,
      queued_for_retraining: true,
      audit_id,
    })
  }),

  // Rules
  http.get(api('/rules'), () => HttpResponse.json(RULES)),
  http.post(api('/rules'), async ({ request }) => {
    const body = (await request.json()) as Partial<(typeof RULES)[number]>
    const rule = {
      id: `rule_${Date.now().toString(16)}`,
      name: body.name ?? 'New rule',
      description: body.description ?? '',
      type: body.type ?? 'threshold',
      enabled: false,
      status: 'pending_approval' as const,
      version: 1,
      params: body.params ?? [],
      updated_by: 'dgm.demo',
      updated_ts: new Date().toISOString(),
    }
    RULES.unshift(rule)
    return HttpResponse.json(rule, { status: 201 })
  }),
  http.put(api('/rules/:id'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as {
      params?: (typeof RULES)[number]['params']
      enabled?: boolean
      summary?: string
    }
    const rule = RULES.find((r) => r.id === id)
    if (!rule) return new HttpResponse('rule not found', { status: 404 })
    // Four-eyes: a change goes to pending_approval, not straight to active.
    rule.status = 'pending_approval'
    rule.version += 1
    if (body.params) rule.params = body.params
    if (typeof body.enabled === 'boolean') rule.enabled = body.enabled
    rule.updated_ts = new Date().toISOString()
    rule.history = [
      {
        version: rule.version,
        status: 'pending_approval',
        proposed_by: 'dgm.demo',
        approved_by: null,
        ts: rule.updated_ts,
        summary: body.summary ?? 'Threshold change proposed — awaiting four-eyes approval',
      },
      ...(rule.history ?? []),
    ]
    recordAudit({
      actor: 'dgm.demo',
      actor_role: 'dgm_compliance',
      action: 'rule_change_proposed',
      target: rule.code ?? rule.id,
    })
    return HttpResponse.json(rule)
  }),

  // Models / drift / metrics
  http.get(api('/models'), () => HttpResponse.json(MODELS)),
  http.post(api('/models/:id/promote'), ({ params }) => {
    const id = String(params.id)
    const m = MODELS.find((x) => x.id === id)
    if (!m) return new HttpResponse('model not found', { status: 404 })
    const audit_id = recordAudit({
      actor: 'datasci.demo',
      actor_role: 'data_science_lead',
      action: 'promote_model',
      target: id,
      outcome: 'pending_signoff',
    })
    return HttpResponse.json({ model_id: id, stage: m.stage, requires_signoff: true, audit_id })
  }),
  http.get(api('/drift'), () => HttpResponse.json(DRIFT)),
  http.get(api('/metrics/model'), () => HttpResponse.json(MODEL_QUALITY)),

  // Reports / coverage / KRIs
  http.get(api('/reports/fmr'), () => HttpResponse.json(reportFor('fmr'))),
  http.get(api('/reports/crilc'), () => HttpResponse.json(reportFor('crilc'))),
  http.get(api('/reports/ews-coverage'), () => HttpResponse.json(EWS_COVERAGE)),
  http.get(api('/reports/kris'), () => HttpResponse.json(KRIS)),

  // Audit
  http.get(api('/audit'), ({ request }) => {
    const url = new URL(request.url)
    const actor = url.searchParams.get('actor')
    const entity = url.searchParams.get('entity')
    const action = url.searchParams.get('action')
    let items = [...AUDIT]
    if (actor) items = items.filter((a) => a.actor.includes(actor))
    if (entity) items = items.filter((a) => a.entity_id === entity)
    if (action) items = items.filter((a) => a.action === action)
    // Paginate like the backend (WORM trail is large): return a page + the full `total`.
    const total = items.length
    const limit = Math.min(Number(url.searchParams.get('limit')) || 1000, 1000)
    const offset = Number(url.searchParams.get('offset')) || 0
    return HttpResponse.json({ items: items.slice(offset, offset + limit), total, limit, offset })
  }),

  // Admin
  http.get(api('/admin/users'), () => HttpResponse.json(USERS)),
  http.post(api('/admin/users'), async ({ request }) => {
    const body = (await request.json()) as CreateUserBody
    const user = {
      id: `u_${Date.now().toString(16)}`,
      username: body.username,
      display_name: body.display_name,
      email: body.email,
      roles: body.roles,
      status: 'active' as const,
      created_ts: new Date().toISOString(),
      last_login: null,
    }
    USERS.push(user)
    recordAudit({
      actor: 'itadmin.demo',
      actor_role: 'it_admin',
      action: 'create_user',
      target: body.username,
    })
    return HttpResponse.json(user, { status: 201 })
  }),

  // Ambient / sub-threshold activity (the 'hidden 95%')
  http.get(api('/activity/sub-threshold'), () => HttpResponse.json(SUB_THRESHOLD)),

  // Management analytics — fraud-typology prevalence + confirmed-rate
  http.get(api('/analytics/typologies'), () => HttpResponse.json(TYPOLOGY_ANALYTICS)),

  // Health / metrics / readiness
  http.get(api('/health'), () => HttpResponse.json(HEALTH)),
  http.get(api('/readyz'), () => HttpResponse.json(READYZ)),
  http.get(
    api('/metrics'),
    () => new HttpResponse(METRICS_TEXT, { headers: { 'Content-Type': 'text/plain' } }),
  ),

  // Cases
  http.get(api('/cases'), () =>
    HttpResponse.json({
      items: CASES.map(({ alerts: _a, notes: _n, history: _h, ...summary }) => summary),
      total: CASES.length,
    }),
  ),
  http.get(api('/cases/:id'), ({ params }) => {
    const c = findCase(String(params.id))
    return c ? HttpResponse.json(c) : new HttpResponse('case not found', { status: 404 })
  }),
  http.post(api('/cases/:id/status'), async ({ params, request }) => {
    const c = findCase(String(params.id))
    if (!c) return new HttpResponse('case not found', { status: 404 })
    const body = (await request.json()) as { status: typeof c.status; note?: string }
    c.status = body.status
    c.updated_ts = new Date().toISOString()
    c.history = [
      {
        id: `h_${Date.now().toString(16)}`,
        ts: c.updated_ts,
        actor: 'rm.demo',
        actor_role: 'relationship_manager',
        action: 'status_changed',
        detail: `→ ${body.status}`,
      },
      ...c.history,
    ]
    return HttpResponse.json(c)
  }),
  http.post(api('/cases/:id/assign'), async ({ params, request }) => {
    const c = findCase(String(params.id))
    if (!c) return new HttpResponse('case not found', { status: 404 })
    const body = (await request.json()) as { assignee: string }
    c.assignee = body.assignee
    c.updated_ts = new Date().toISOString()
    return HttpResponse.json(c)
  }),
  http.post(api('/cases/:id/notes'), async ({ params, request }) => {
    const c = findCase(String(params.id))
    if (!c) return new HttpResponse('case not found', { status: 404 })
    const body = (await request.json()) as { body: string }
    c.notes = [
      ...c.notes,
      {
        id: `n_${Date.now().toString(16)}`,
        author: 'rm.demo',
        author_role: 'relationship_manager',
        ts: new Date().toISOString(),
        body: body.body,
      },
    ]
    c.updated_ts = new Date().toISOString()
    return HttpResponse.json(c)
  }),
]
