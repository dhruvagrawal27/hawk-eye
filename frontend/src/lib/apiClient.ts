/**
 * Typed API client — one method per `BACKEND.md` §3 route. **Components call these, never `fetch`
 * directly** (prompt §3 stub rule: one seam, flip mock↔real with `VITE_USE_MOCKS`).
 *
 * Routes with [FE-proposed] response/request shapes (cases, ews-coverage, kris) or paths that
 * BACKEND.md lists by family but not by exact sub-path (rules PUT, cases) are flagged in CONTEXT.md
 * (2026-06-30 — [FRONTEND]). They bind to MSW today and to BACKEND when finalised.
 */
import { env } from './env'
import { request } from './http'
import type {
  AdminUser,
  Alert,
  AlertStats,
  LayerScoresResponse,
  SubThresholdResponse,
  TypologyAnalyticsResponse,
  AlertQuery,
  AssignBody,
  AssignResponse,
  AuditEvent,
  AuditQuery,
  BlockRequestBody,
  BlockRequestResponse,
  CaseDetail,
  CaseSummary,
  CreateUserBody,
  DispositionRequest,
  DispositionResponse,
  DriftResponse,
  EntityProfile,
  EwsCoverageResponse,
  ExplanationResponse,
  FeedbackBody,
  FeedbackResponse,
  GraphOverviewResponse,
  GraphResponse,
  HealthResponse,
  KriResponse,
  ModelEntry,
  ModelMetrics,
  ModelPromoteResponse,
  ModelQualityResponse,
  ModelStage,
  NarrativeMemo,
  PromoteRequestBody,
  RawDriftReport,
  RawHealth,
  RawModelInfo,
  RawModelQuality,
  RawPromoteResult,
  ServiceHealth,
  ServiceStatusResponse,
  Paginated,
  AttestationDetail,
  PeerComparisonResponse,
  RiskIndex,
  ActionHold,
  ActionHoldList,
  ActionPolicy,
  HoldDecisionBody,
  ReportExport,
  Rule,
  RuleParam,
  ScoreHistoryResponse,
  TimelineResponse,
  TokenResponse,
  UnmaskBody,
  UnmaskResponse,
} from './types'

/* ──────────────────────────────────────────────────────────────────────────────────────────────
 * Adapters — normalise the LIVE backend's flat model/drift/health shapes into the render shapes the
 * components already consume. Each is defensive: a shape surprise degrades one panel, never the app.
 * ────────────────────────────────────────────────────────────────────────────────────────────── */

/** Live registry `stage` ("Production"/"Challenger"/…) → the UI's champion/challenger/staging/archived. */
function mapStage(stage: string | undefined): ModelStage {
  switch ((stage ?? '').toLowerCase()) {
    case 'production':
    case 'champion':
      return 'champion'
    case 'challenger':
      return 'challenger'
    case 'staging':
      return 'staging'
    default:
      return 'archived'
  }
}

/** A readable display name from the flat `model_id` (e.g. "l3_lightgbm" → "L3 lightgbm"). */
function modelDisplayName(modelId: string): string {
  const s = modelId.replace(/_/g, ' ').trim()
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : modelId
}

/** Live metrics bag → the typed ModelMetrics the UI knows (extra keys pass through untouched). */
function adaptMetrics(raw: Record<string, number> | null | undefined): ModelMetrics {
  return { ...(raw ?? {}) }
}

/** One live registry row → the ModelEntry the registry table renders. */
function adaptModel(m: RawModelInfo): ModelEntry {
  return {
    id: m.model_id,
    name: modelDisplayName(m.model_id),
    layer: m.layer,
    version: m.version,
    stage: mapStage(m.stage),
    signed: Boolean(m.signed),
    promoted_by: m.approving_reviewer ?? null,
    // The live registry does not carry a created timestamp; fall back to the version tag.
    created_ts: m.version,
    metrics: adaptMetrics(m.metrics),
    de_identified: true,
  }
}

function isRawModelInfo(v: unknown): v is RawModelInfo {
  return typeof v === 'object' && v !== null && typeof (v as RawModelInfo).model_id === 'string'
}

/** The live flat `/health` dict has no `services[]` array — the render-shape one does. */
function isRenderHealth(v: unknown): v is HealthResponse {
  return typeof v === 'object' && v !== null && Array.isArray((v as HealthResponse).services)
}

/** Flat live `/health` dict → the {status, services[], checked_ts} shape the panel renders. */
function adaptHealth(raw: RawHealth): HealthResponse {
  const overall: HealthResponse['status'] =
    raw.status === 'ok' && raw.serving_ready !== false
      ? raw.degraded_l1_only
        ? 'degraded'
        : 'ok'
      : raw.serving_ready === false
        ? 'down'
        : 'degraded'

  const services: ServiceHealth[] = [
    {
      name: raw.service ?? 'hawk-eye-api',
      status: raw.serving_ready === false ? 'down' : 'ok',
      detail: raw.env ? `env: ${raw.env}` : undefined,
    },
    {
      name: 'Scoring pipeline (L1–L6)',
      status: raw.degraded_l1_only ? 'degraded' : raw.serving_ready === false ? 'down' : 'ok',
      detail: raw.degraded_l1_only
        ? 'Degraded — L1 rules only (ML layers unavailable)'
        : 'All layers serving',
    },
    {
      name: 'Internal mTLS',
      status: raw.mtls_internal ? 'ok' : 'degraded',
      detail: raw.mtls_internal ? 'Mutual TLS enforced' : 'mTLS not enforced',
    },
    {
      name: 'Authentication',
      status: 'ok',
      detail: raw.auth_mode ? `mode: ${raw.auth_mode}` : undefined,
    },
  ]

  return { status: overall, version: raw.version, services, checked_ts: new Date().toISOString() }
}

export const apiClient = {
  /* ── Auth (BACKEND.md §3 public) ───────────────────────────────────────── */
  login(body: { username: string; password?: string; code?: string }): Promise<TokenResponse> {
    return request('/auth/login', { method: 'POST', body })
  },
  refresh(body?: { refresh_token?: string }): Promise<TokenResponse> {
    return request('/auth/refresh', { method: 'POST', body: body ?? {} })
  },

  /* ── Alerts / triage / EDD actions ─────────────────────────────────────── */
  listAlerts(query: AlertQuery = {}): Promise<Paginated<Alert>> {
    return request('/alerts', {
      query: {
        status: query.status,
        risk_gte: query.risk_gte,
        assignee: query.assignee,
        type: query.type,
        page: query.page,
        page_size: query.page_size,
      },
    })
  },
  getAlert(id: string): Promise<Alert> {
    return request(`/alerts/${encodeURIComponent(id)}`)
  },
  /** Portfolio counts for the dashboard header (open / high / SLA-at-risk), computed server-side. */
  getAlertStats(): Promise<AlertStats> {
    return request('/alerts/stats')
  },
  assignAlert(id: string, body: AssignBody): Promise<AssignResponse> {
    return request(`/alerts/${encodeURIComponent(id)}/assign`, { method: 'POST', body })
  },
  dispositionAlert(id: string, body: DispositionRequest): Promise<DispositionResponse> {
    return request(`/alerts/${encodeURIComponent(id)}/disposition`, { method: 'POST', body })
  },
  /** A *request* routed to a Lead for approval — never an auto-block (golden rule #1). */
  blockRequest(id: string, body: BlockRequestBody): Promise<BlockRequestResponse> {
    return request(`/alerts/${encodeURIComponent(id)}/block-request`, { method: 'POST', body })
  },

  /* ── Entity-360 ────────────────────────────────────────────────────────── */
  getEntity(id: string): Promise<EntityProfile> {
    return request(`/entities/${encodeURIComponent(id)}`)
  },
  getEntityTimeline(id: string): Promise<TimelineResponse> {
    return request(`/entities/${encodeURIComponent(id)}/timeline`)
  },
  /** `depth` widens the subgraph by N hops (depth-expand control); the server clamps the radius. */
  getEntityGraph(id: string, opts: { depth?: number } = {}): Promise<GraphResponse> {
    return request(`/entities/${encodeURIComponent(id)}/graph`, { query: { depth: opts.depth } })
  },
  getEntityPeers(id: string): Promise<PeerComparisonResponse> {
    return request(`/entities/${encodeURIComponent(id)}/peers`)
  },
  /** M2.1 continuous per-user insider-risk index (0–100, sub-scores + drivers). Alert-only. */
  getRiskIndex(id: string): Promise<RiskIndex> {
    return request(`/entities/${encodeURIComponent(id)}/risk-index`)
  },

  /* ── L6.5 privileged-action interdiction console (M3.4) ─────────────────── */
  listActionHolds(): Promise<ActionHoldList> {
    return request('/action-gate/holds')
  },
  /** Four-eyes decision on a held staff action (approve = PERMIT human execution; never auto-runs). */
  decideActionHold(holdId: string, body: HoldDecisionBody): Promise<ActionHold> {
    return request(`/action-gate/holds/${encodeURIComponent(holdId)}/decision`, {
      method: 'POST',
      body,
    })
  },
  listActionPolicies(): Promise<ActionPolicy[]> {
    return request('/action-gate/policies')
  },
  /** [FE-proposed] 0–100 fused-risk-score history for the entity (ScoreOverTime on AlertDetail). */
  getScoreHistory(id: string): Promise<ScoreHistoryResponse> {
    return request(`/entities/${encodeURIComponent(id)}/score-history`)
  },
  /**
   * [FE-proposed] GET /graph — global top-risk subgraph for the Graph Explorer. `minScore` filters
   * the seed entities by risk; `limit` caps the seed count. One-line swap to the real route later.
   */
  getGraphOverview(
    opts: { minScore?: number; limit?: number } = {},
  ): Promise<GraphOverviewResponse> {
    return request('/graph', { query: { min_score: opts.minScore, limit: opts.limit } })
  },
  /**
   * Audited re-identification (Part 25.3). Server logs it; UI surfaces the audit_id. The live
   * response is `{entity_id, mapping:{token→value}, audit_id}`; older/MSW shape is a single `value`.
   * Normalise so `mapping` is always populated for consumers.
   */
  async unmaskEntity(id: string, body: UnmaskBody = {}): Promise<UnmaskResponse> {
    const res = await request<UnmaskResponse>(`/entities/${encodeURIComponent(id)}/unmask`, {
      method: 'POST',
      body,
    })
    if (res.mapping && Object.keys(res.mapping).length > 0) return res
    // Fold a legacy single-value response into the mapping shape (keyed by its token / entity id).
    if (res.value != null) {
      return { ...res, mapping: { [res.token ?? res.entity_id]: res.value } }
    }
    return { ...res, mapping: res.mapping ?? {} }
  },

  /* ── Explanation + narrative ───────────────────────────────────────────── */
  async getExplanation(alertId: string): Promise<ExplanationResponse> {
    // The LIVE backend returns `rule_provenance`/`sequence_attention`; the render shape (+ MSW mock)
    // uses `rules`/`attention`. Normalize both so the panels populate in live AND mock mode.
    const raw = await request<Record<string, unknown>>(
      `/explanations/${encodeURIComponent(alertId)}`,
    )
    return {
      alert_id: raw.alert_id as string,
      shap: (raw.shap as ExplanationResponse['shap']) ?? [],
      rules: (raw.rules ?? raw.rule_provenance ?? []) as ExplanationResponse['rules'],
      attention: (raw.attention ?? raw.sequence_attention ?? []) as ExplanationResponse['attention'],
      graph: raw.graph as ExplanationResponse['graph'],
      fusion: raw.fusion as ExplanationResponse['fusion'],
      model_lineage: raw.model_lineage as ExplanationResponse['model_lineage'],
    }
  },
  /** POST per BACKEND.md §3/§7 — gateway runs at call time; deterministic template fallback guarantees a body. */
  getNarrative(alertId: string): Promise<NarrativeMemo> {
    return request(`/narratives/${encodeURIComponent(alertId)}`, { method: 'POST', body: {} })
  },
  /**
   * [FE-proposed] Per-request TEE attestation detail for a narrative (Part 25). Lazily fetched by
   * ProvenanceBadge only when the narrative reports `tee_attested`.
   */
  getAttestation(alertId: string): Promise<AttestationDetail> {
    return request(`/narratives/${encodeURIComponent(alertId)}/attestation`)
  },

  /** Service map — every platform service, what it's for, where it's used, and live status. */
  getServiceStatus(): Promise<ServiceStatusResponse> {
    return request('/services/status')
  },
  /** Sub-threshold ('hidden 95%') activity — detection funnel + near-miss watchlist (scored < 70). */
  getSubThreshold(limit = 20): Promise<SubThresholdResponse> {
    return request(`/activity/sub-threshold?limit=${limit}`)
  },
  /** Fraud-typology prevalence + confirmed-rate + exposure (management analytics). */
  getTypologyAnalytics(): Promise<TypologyAnalyticsResponse> {
    return request('/analytics/typologies')
  },
  /** Per-layer score timeline for an entity — one series per detection layer (hawkeye.scores). */
  getLayerScores(entityId: string): Promise<LayerScoresResponse> {
    return request(`/entities/${encodeURIComponent(entityId)}/layer-scores`)
  },
  /** Downloadable, audit-grade explainability report for one alert (SAR/FMR evidence pack). */
  getExplanationReport(alertId: string): Promise<Record<string, unknown>> {
    return request(`/explanations/${encodeURIComponent(alertId)}/report`)
  },

  /* ── Active-learning feedback (Part 10 relabel loop) ───────────────────── */
  submitFeedback(body: FeedbackBody): Promise<FeedbackResponse> {
    return request('/feedback', { method: 'POST', body })
  },

  /* ── Rules (change-controlled; four-eyes server-side) ──────────────────── */
  listRules(): Promise<Rule[]> {
    return request('/rules')
  },
  createRule(body: Partial<Rule>): Promise<Rule> {
    return request('/rules', { method: 'POST', body })
  },
  updateRule(
    id: string,
    body: { params?: RuleParam[]; enabled?: boolean; summary?: string },
  ): Promise<Rule> {
    return request(`/rules/${encodeURIComponent(id)}`, { method: 'PUT', body })
  },

  /* ── Models / drift / quality (de-identified) ──────────────────────────── */
  async listModels(): Promise<ModelEntry[]> {
    // Live `/models` returns raw registry rows ({model_id, stage:"Production", metrics:{…}}); MSW
    // returns the FE render shape already. Adapt raw rows, pass render rows through unchanged.
    const rows = await request<unknown>('/models')
    if (!Array.isArray(rows)) return []
    return rows.map((r) => (isRawModelInfo(r) ? adaptModel(r) : (r as ModelEntry)))
  },
  /**
   * Promote a model artifact. The live route is
   * `POST /models/{id}/promote?version=…` with body `{to_stage, signoff_by, canary_percent?}` —
   * SoD requires `signoff_by ≠ requester`. Returns a normalised {model_id, stage, requires_signoff}.
   */
  async promoteModel(
    id: string,
    opts: { version: string; toStage?: string; signoffBy: string; canaryPercent?: number },
  ): Promise<ModelPromoteResponse> {
    const body: PromoteRequestBody = {
      to_stage: opts.toStage ?? 'Production',
      signoff_by: opts.signoffBy,
      canary_percent: opts.canaryPercent,
    }
    const res = await request<RawPromoteResult>(`/models/${encodeURIComponent(id)}/promote`, {
      method: 'POST',
      query: { version: opts.version },
      body,
    })
    return {
      model_id: res.model_id,
      stage: mapStage(res.stage),
      requires_signoff: true,
      audit_id: res.audit_id,
    }
  },
  async getDrift(): Promise<DriftResponse> {
    // Live `/drift` is a flat single-model report; MSW serves the multi-series render shape.
    const raw = await request<RawDriftReport | DriftResponse>('/drift')
    if (raw && Array.isArray((raw as DriftResponse).series)) return raw as DriftResponse
    const d = raw as RawDriftReport
    const status = d.drift_crossed ? 'drifting' : d.data_drift_psi >= 0.1 ? 'warning' : 'ok'
    const now = new Date().toISOString()
    return {
      generated_ts: now,
      series: [
        {
          model_id: d.model_id,
          feature: 'population_stability',
          metric: 'psi',
          status,
          points: [{ ts: now, value: d.data_drift_psi, threshold: 0.2 }],
        },
        {
          model_id: d.model_id,
          feature: 'concept_drift',
          metric: 'js',
          status: d.drift_crossed ? 'drifting' : d.concept_drift >= 0.1 ? 'warning' : 'ok',
          points: [{ ts: now, value: d.concept_drift, threshold: 0.1 }],
        },
      ],
    }
  },
  async getModelMetrics(): Promise<ModelQualityResponse> {
    // Live `/metrics/model` is a flat single-model snapshot; MSW serves the multi-row render shape.
    const raw = await request<RawModelQuality | ModelQualityResponse>('/metrics/model')
    if (raw && Array.isArray((raw as ModelQualityResponse).models)) {
      return raw as ModelQualityResponse
    }
    const q = raw as RawModelQuality
    const metrics: ModelMetrics = {}
    if (q.pr_auc != null) metrics.pr_auc = q.pr_auc
    if (q.precision_at_k != null) metrics.precision_at_k = q.precision_at_k
    if (q.calibration_error != null) metrics.calibration_error = q.calibration_error
    if (q.alert_to_true_fraud_ratio != null)
      metrics.alert_to_true_fraud_ratio = q.alert_to_true_fraud_ratio
    return { models: [{ model_id: q.model_id, metrics }] }
  },

  /* ── Regulatory exports + coverage + KRIs ──────────────────────────────── */
  getFmrReport(): Promise<ReportExport> {
    return request('/reports/fmr')
  },
  getCrilcReport(): Promise<ReportExport> {
    return request('/reports/crilc')
  },
  /** [FE-proposed] EWS/RFA indicator coverage map (Part 24.4 screen 5). */
  getEwsCoverage(): Promise<EwsCoverageResponse> {
    return request('/reports/ews-coverage')
  },
  /** [FE-proposed] management + board KRI dashboard (Part 24.4 / Part 11 reporting). */
  getKris(): Promise<KriResponse> {
    return request('/reports/kris')
  },

  /* ── Audit (read-only WORM trail) ──────────────────────────────────────── */
  getAudit(query: AuditQuery = {}): Promise<Paginated<AuditEvent>> {
    return request('/audit', {
      query: {
        actor: query.actor,
        entity: query.entity,
        from: query.from,
        to: query.to,
        action: query.action,
        page: query.page,
        page_size: query.page_size,
      },
    })
  },

  /* ── Admin ─────────────────────────────────────────────────────────────── */
  listUsers(): Promise<AdminUser[]> {
    return request('/admin/users')
  },
  createUser(body: CreateUserBody): Promise<AdminUser> {
    return request('/admin/users', { method: 'POST', body })
  },

  /* ── Health / metrics ──────────────────────────────────────────────────── */
  async getHealth(): Promise<HealthResponse> {
    // The live backend serves `/health` at the server ROOT (a flat status dict), NOT under the
    // `/api/v1` base — hitting `/api/v1/health` 404s. Bypass the base against a real backend; under
    // MSW keep the base path so the mock (registered at `${base}/health`) still intercepts.
    const raw = await request<RawHealth | HealthResponse>('/health', {
      rootPath: !env.useMocks,
    })
    return isRenderHealth(raw) ? raw : adaptHealth(raw)
  },
  getMetrics(): Promise<string> {
    return request('/metrics', { responseType: 'text' })
  },

  /* ── Cases [FE-proposed: /cases not yet in BACKEND.md §3 — flagged in CONTEXT.md] ── */
  listCases(): Promise<Paginated<CaseSummary>> {
    return request('/cases')
  },
  getCase(id: string): Promise<CaseDetail> {
    return request(`/cases/${encodeURIComponent(id)}`)
  },
  updateCaseStatus(
    id: string,
    body: { status: CaseSummary['status']; note?: string },
  ): Promise<CaseDetail> {
    return request(`/cases/${encodeURIComponent(id)}/status`, { method: 'POST', body })
  },
  assignCase(id: string, body: { assignee: string }): Promise<CaseDetail> {
    return request(`/cases/${encodeURIComponent(id)}/assign`, { method: 'POST', body })
  },
  addCaseNote(id: string, body: { body: string }): Promise<CaseDetail> {
    return request(`/cases/${encodeURIComponent(id)}/notes`, { method: 'POST', body })
  },
} as const

export type ApiClient = typeof apiClient
