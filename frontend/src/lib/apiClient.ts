/**
 * Typed API client — one method per `BACKEND.md` §3 route. **Components call these, never `fetch`
 * directly** (prompt §3 stub rule: one seam, flip mock↔real with `VITE_USE_MOCKS`).
 *
 * Routes with [FE-proposed] response/request shapes (cases, ews-coverage, kris) or paths that
 * BACKEND.md lists by family but not by exact sub-path (rules PUT, cases) are flagged in CONTEXT.md
 * (2026-06-30 — [FRONTEND]). They bind to MSW today and to BACKEND when finalised.
 */
import { request } from './http'
import type {
  AdminUser,
  Alert,
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
  ModelPromoteResponse,
  ModelQualityResponse,
  NarrativeMemo,
  Paginated,
  PeerComparisonResponse,
  ReportExport,
  Rule,
  RuleParam,
  TimelineResponse,
  TokenResponse,
  UnmaskBody,
  UnmaskResponse,
} from './types'

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
  /**
   * [FE-proposed] GET /graph — global top-risk subgraph for the Graph Explorer. `minScore` filters
   * the seed entities by risk; `limit` caps the seed count. One-line swap to the real route later.
   */
  getGraphOverview(
    opts: { minScore?: number; limit?: number } = {},
  ): Promise<GraphOverviewResponse> {
    return request('/graph', { query: { min_score: opts.minScore, limit: opts.limit } })
  },
  /** Audited re-identification (Part 25.3). Server logs it; UI surfaces the audit_id. */
  unmaskEntity(id: string, body: UnmaskBody = {}): Promise<UnmaskResponse> {
    return request(`/entities/${encodeURIComponent(id)}/unmask`, { method: 'POST', body })
  },

  /* ── Explanation + narrative ───────────────────────────────────────────── */
  getExplanation(alertId: string): Promise<ExplanationResponse> {
    return request(`/explanations/${encodeURIComponent(alertId)}`)
  },
  /** POST per BACKEND.md §3/§7 — gateway runs at call time; deterministic template fallback guarantees a body. */
  getNarrative(alertId: string): Promise<NarrativeMemo> {
    return request(`/narratives/${encodeURIComponent(alertId)}`, { method: 'POST', body: {} })
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
  listModels(): Promise<ModelEntry[]> {
    return request('/models')
  },
  promoteModel(id: string): Promise<ModelPromoteResponse> {
    return request(`/models/${encodeURIComponent(id)}/promote`, { method: 'POST', body: {} })
  },
  getDrift(): Promise<DriftResponse> {
    return request('/drift')
  },
  getModelMetrics(): Promise<ModelQualityResponse> {
    return request('/metrics/model')
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
  getHealth(): Promise<HealthResponse> {
    return request('/health')
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
