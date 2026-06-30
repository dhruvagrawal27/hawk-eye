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
  AuditEvent,
  BlockRequestResponse,
  DispositionRequest,
  DispositionResponse,
  ExplanationResponse,
  GraphResponse,
  PeerComparisonResponse,
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
  KRIS,
  METRICS_TEXT,
  MODELS,
  MODEL_QUALITY,
  PEERS,
  RULES,
  TIMELINES,
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

function buildExplanation(alertId: string): ExplanationResponse {
  if (EXPLANATIONS[alertId]) return EXPLANATIONS[alertId]
  const a = findAlert(alertId)
  const reasons = a?.reason_codes ?? []
  return {
    alert_id: alertId,
    shap: reasons
      .filter((r): r is Extract<typeof r, { source: 'shap' }> => r.source === 'shap')
      .map((r) => ({
        feature: r.feature,
        contribution: r.contribution,
        direction: r.contribution >= 0 ? 'increases_risk' : 'decreases_risk',
      })),
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

function buildGraph(entityId: string): GraphResponse {
  if (GRAPHS[entityId]) return GRAPHS[entityId]
  return {
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
  http.get(api('/alerts/:id'), ({ params }) => {
    const a = findAlert(String(params.id))
    return a ? HttpResponse.json(a) : new HttpResponse('alert not found', { status: 404 })
  }),
  http.post(api('/alerts/:id/assign'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as { assignee?: string }
    const a = findAlert(id)
    if (!a) return new HttpResponse('alert not found', { status: 404 })
    a.assignee = body.assignee ?? 'analyst.demo'
    if (a.status === 'open') a.status = 'assigned'
    const audit_id = recordAudit({
      actor: a.assignee,
      actor_role: 'analyst',
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
      actor: 'analyst.demo',
      actor_role: 'analyst',
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
      actor: 'analyst.demo',
      actor_role: 'analyst',
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
  http.get(api('/entities/:id/graph'), ({ params }) =>
    HttpResponse.json(buildGraph(String(params.id))),
  ),
  http.get(api('/entities/:id/peers'), ({ params }) =>
    HttpResponse.json(buildPeers(String(params.id))),
  ),
  http.post(api('/entities/:id/unmask'), async ({ params, request }) => {
    const id = String(params.id)
    const body = (await request.json().catch(() => ({}))) as { alert_id?: string }
    recordAudit({
      actor: 'senior.demo',
      actor_role: 'senior_investigator',
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

  // Feedback
  http.post(api('/feedback'), async ({ request }) => {
    const body = (await request.json().catch(() => ({}))) as { alert_id?: string }
    const audit_id = recordAudit({
      actor: 'analyst.demo',
      actor_role: 'analyst',
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
      updated_by: 'compliance.demo',
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
        proposed_by: 'compliance.demo',
        approved_by: null,
        ts: rule.updated_ts,
        summary: body.summary ?? 'Threshold change proposed — awaiting four-eyes approval',
      },
      ...(rule.history ?? []),
    ]
    recordAudit({
      actor: 'compliance.demo',
      actor_role: 'compliance_officer',
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
      actor: 'modeleng.demo',
      actor_role: 'model_engineer',
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
    return HttpResponse.json({ items, total: items.length })
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
      actor: 'admin.demo',
      actor_role: 'platform_admin',
      action: 'create_user',
      target: body.username,
    })
    return HttpResponse.json(user, { status: 201 })
  }),

  // Health / metrics
  http.get(api('/health'), () => HttpResponse.json(HEALTH)),
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
        actor: 'analyst.demo',
        actor_role: 'analyst',
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
        author: 'analyst.demo',
        author_role: 'analyst',
        ts: new Date().toISOString(),
        body: body.body,
      },
    ]
    c.updated_ts = new Date().toISOString()
    return HttpResponse.json(c)
  }),
]
