/**
 * Hawk-Eye API contract types — the single typed mirror of `BACKEND.md` (owned by BACKEND).
 *
 * Provenance:
 *  - Shapes marked **[BACKEND.md]** are byte-for-byte the canonical contract (§1 event, §2 alert,
 *    §5 disposition, §7 narrative memo, §3 routes, §4 RBAC) and the Part 24.5 sample payloads.
 *    Do NOT invent fields on these.
 *  - Shapes marked **[FE-proposed]** cover endpoints listed in BACKEND.md §3 whose response bodies
 *    are not yet byte-specified (explanations, graph, peers, rules, models, drift, audit, admin,
 *    reports). They are rendered against, served by MSW, and proposed to BACKEND in CONTEXT.md
 *    (2026-06-30 — [FRONTEND] — proposed render shapes for under-specified endpoints). When BACKEND
 *    finalises them, reconcile here — components bind only to these names.
 *
 * IDs (CONTEXT.md §6): evt_* / alr_* / EMP-* / RNG-* / aud_*. Time: UTC ISO-8601 (stored), IST
 * (displayed — see format.ts). Money: INR, integer rupees in `exposure_inr` / `amount`.
 */

/* ───────────────────────────── ID aliases (documentation, not branding) ──────────────────── */
export type EventId = string // evt_*
export type AlertId = string // alr_*
export type EntityId = string // EMP-* (entity_id == employee_id)
export type RingId = string // RNG-*
export type AuditId = string // aud_*
export type IsoTimestamp = string // UTC ISO-8601, e.g. "2026-06-30T02:41:55Z"

/* ───────────────────────────── RBAC roles [BANK_ROLES.md / BACKEND.md §4 / Part 24.1] ──────── */
// Bank org-chart console/RBAC roles (12: 11 human + 1 service), mapped onto RBI's Three Lines of
// Defense. FROZEN — see docs/BANK_ROLES.md. (Distinct from actor/subject roles in data/sim/*.)
export type Role =
  | 'relationship_manager'
  | 'branch_manager'
  | 'cluster_head'
  | 'agm_vigilance'
  | 'dgm_compliance'
  | 'data_science_lead'
  | 'cgm_risk'
  | 'chief_internal_auditor'
  | 'executive_director'
  | 'managing_director'
  | 'it_admin'
  | 'service_account'

/* ───────────────────────────── L0 unified event [BACKEND.md §1 / Part 24.5a] ──────────────── */
export type EventLayer = 'application' | 'data' | 'identity' | 'change'
export type MakerChecker = 'maker' | 'checker' | null
/** Derived family used by the entity-360 timeline grouping (FRONTEND-7). */
export type EventFamily = 'transaction' | 'access' | 'data' | 'change'

export interface EventActor {
  employee_id: EntityId
  role: string
  dept: string
  branch: string
  tenure_days: number
  peer_group: string
  privileged_flag: boolean
  leaver_flag: boolean
}

export interface EventAction {
  verb: string
  channel: string
  maker_checker: MakerChecker
}

export interface EventObject {
  beneficiary_id: string | null
  account_id: string | null
  amount: number | null
  currency: string
}

export interface EventContext {
  src_ip: string
  device: string
  geo: string
  session_id: string
  layer: EventLayer | string
  is_off_hours: boolean
}

export interface UnifiedEvent {
  event_id: EventId
  ts: IsoTimestamp
  actor: EventActor
  action: EventAction
  object: EventObject
  context: EventContext
}

/* ───────────────────────────── L6 alert [BACKEND.md §2 / Part 24.5b] ──────────────────────── */
export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type AlertStatus =
  | 'open'
  | 'assigned'
  | 'in_progress'
  | 'escalated'
  | 'confirmed_fraud'
  | 'false_positive'
  | 'inconclusive'
  | 'closed'
export type ContributingLayer =
  'L1_rules' | 'L2_unsupervised' | 'L3_gbdt' | 'L4_sequence' | 'L5_graph' | 'L6_fusion'

export type ReasonCodeSource = 'rule' | 'shap' | 'graph'
export type ReasonCode =
  | { source: 'rule'; code: string; detail: string }
  | { source: 'shap'; feature: string; contribution: number }
  | { source: 'graph'; detail: string; ring_id?: RingId }

export interface Alert {
  alert_id: AlertId
  entity_id: EntityId
  risk_score: number // 0–100 calibrated
  severity: Severity
  confidence: number // 0–1
  status: AlertStatus
  created_ts: IsoTimestamp
  contributing_layers: (ContributingLayer | string)[]
  reason_codes: ReasonCode[]
  exposure_inr: number
  sla_due_ts: IsoTimestamp
  pii_tokenized: boolean
  // Optional fields the queue/store may attach (BACKEND.md filters imply assignee; dedup is a
  // queue affordance). All optional so the strict Part 24.5b shape still validates.
  assignee?: string | null
  alert_type?: string
  title?: string
  /** Number of alerts collapsed into this entity row when the queue dedups per entity. */
  duplicate_count?: number
}

/** Paginated list envelope used by `GET /alerts` (and other list routes). */
export interface Paginated<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
}

export interface AlertQuery {
  status?: AlertStatus
  risk_gte?: number
  assignee?: string
  type?: string
  page?: number
  page_size?: number
}

/* ───────────────────────────── Entity-360 [BACKEND.md §3 routes] ──────────────────────────── */
/** [FE-proposed] GET /entities/{id} */
export interface EntityProfile {
  entity_id: EntityId
  employee_id: EntityId
  display_name: string // tokenized unless unmasked
  role: string
  dept: string
  branch: string
  tenure_days: number
  peer_group: string
  privileged_flag: boolean
  leaver_flag: boolean
  risk_score: number
  status?: string
  manager_id?: EntityId | null
  joined_ts?: IsoTimestamp
  pii_tokenized: boolean
  open_alert_count?: number
}

/** [FE-proposed] GET /entities/{id}/timeline — L0 events plus a derived family for grouping. */
export interface TimelineEntry extends UnifiedEvent {
  family?: EventFamily
}
export interface TimelineResponse {
  entity_id: EntityId
  events: TimelineEntry[]
}

/* ───────────────────────────── Explanations [BACKEND.md §3 / Part 24.5b + 11] ─────────────── */
/** [FE-proposed] GET /explanations/{alert_id} — SHAP + rule provenance + attention + graph evidence. */
export interface ShapContribution {
  feature: string
  contribution: number // signed; |contribution| drives sort
  value?: number | string
  direction?: 'increases_risk' | 'decreases_risk'
  /** 0–1 percentile of this feature's value vs the peer baseline (e.g. 0.96 = top 4%). */
  percentile?: number
}
export interface RuleProvenanceItem {
  code: string
  detail: string
  typology?: string // e.g. "NEW_BENEFICIARY_THEN_HIGHVALUE" → SoD / typology family
  sod_rule?: string
  severity?: Severity
  layer?: ContributingLayer | string
}
/** One variable's attention weight at a step — the *variable* axis of LAXCAT's variable×temporal map. */
export interface AttentionVariable {
  name: string // e.g. "log_amount", "off_hours", "verb", "velocity_1h"
  weight: number // 0–1 variable-attention weight at this step
}
export interface AttentionStep {
  event_id?: EventId
  ts: IsoTimestamp
  label: string // human label, e.g. "create_beneficiary"
  weight: number // 0–1 temporal attention weight (LAXCAT time axis)
  verb?: string
  channel?: string
  is_off_hours?: boolean
  /** per-variable attention at this step (the variable axis). Enables the variable×temporal heatmap. */
  variables?: AttentionVariable[]
}
export interface AttentionSession {
  session_id: string
  model?: string // e.g. "LAXCAT"
  steps: AttentionStep[]
}
export interface GraphEvidenceNodeRef {
  id: string
  label: string
  type: string
  importance?: number
}
export interface GraphEvidenceEdgeRef {
  source: string
  target: string
  type: string
  importance?: number
}
export interface GraphEvidence {
  ring_id?: RingId
  summary: string
  explainer_model?: string // e.g. "GNNExplainer"
  nodes: GraphEvidenceNodeRef[]
  edges: GraphEvidenceEdgeRef[]
}

/**
 * [FE-proposed] L6 fusion breakdown — the headline "why this fired": the fused score against the
 * decision threshold, decomposed into the per-layer probabilities that the fusion meta-learner
 * weighed (L3 GBDT, L5 graph, L2 unsupervised). `weight` is the meta-learner's coefficient for that
 * layer; `proba` is the layer's own 0–1 output (null when a layer did not contribute). The
 * "rescued by graph fusion" insight (GBDT alone would have missed it) is derived client-side from
 * the GBDT component vs `threshold` — see lib/fusion.ts.
 */
export type FusionLayer =
  | 'L1_rule'
  | 'L2_unsupervised'
  | 'L3_gbdt'
  | 'L4_sequence'
  | 'L5_graph'
export interface FusionComponent {
  layer: FusionLayer | ContributingLayer | string
  label: string // e.g. "Gradient-boosted trees"
  sublabel: string // e.g. "supervised · tabular"
  proba: number | null // 0–1 layer output; null if the layer did not run
  weight: number // meta-learner coefficient for this layer in the fusion
  /** weight × proba — the layer's weighted pull on the fused score (0 when it did not run). */
  contribution?: number
}
export interface FusionBreakdown {
  fused: number // 0–1 fused probability (the meta-learner output)
  threshold: number // decision threshold on the same 0–1 scale
  components: FusionComponent[]
  /** 0–100 calibrated score (round(fused × 100)). */
  calibrated_score?: number
  /** 0–1 cross-layer agreement (tight spread across layers ⇒ higher). */
  agreement?: number
  /** 0–1 blended confidence (agreement × prob). */
  confidence?: number
  /** true when a hard L1 rule forced the alert (no ML needed). */
  hard_hit?: boolean
  /** true when GBDT alone would have missed it but another layer carried it over the line. */
  rescued?: boolean
  /** the fired layer with the strongest weighted pull (the "decisive" driver). */
  decisive_layer?: FusionLayer | string | null
  /** the L6 meta-model version that produced this blend. */
  meta_version?: string
}
/** Which model produced a layer's score + its governance posture (MRMF / FREE-AI). */
export interface ModelLineageEntry {
  layer: string // L1_rule | L2_unsupervised | L3_gbdt | L4_sequence | L5_graph | L6_fusion
  model_id: string
  version: string
  stage: string // Production | Staging | Challenger | Archived
  risk_tier?: string | null
  signed: boolean
  approving_reviewer?: string | null
  metrics?: Record<string, number>
}
export interface ExplanationResponse {
  alert_id: AlertId
  shap: ShapContribution[]
  rules: RuleProvenanceItem[]
  attention: AttentionSession[]
  graph?: GraphEvidence
  /** [FE-proposed] L6 fusion decomposition driving ScoreComposition (the top "why this fired"). */
  fusion?: FusionBreakdown
  /** per-layer model provenance + governance posture (which model fired this, who signed it). */
  model_lineage?: ModelLineageEntry[]
}

/* ───────────────────────────── Management analytics [GET /analytics/typologies] ──────────────── */
/** Per-typology prevalence + confirmed-rate + exposure — the portfolio oversight view. */
export interface TypologyStat {
  typology: string
  label: string
  layers: string[] // detection layers that catch it, e.g. ["L1","L3","L5"]
  alerts: number
  confirmed: number
  false_positive: number
  open: number
  confirmed_rate: number // 0–1
  exposure_inr: number
}
export interface TypologyTotals {
  alerts: number
  confirmed: number
  false_positive: number
  open: number
  confirmed_rate: number
  exposure_inr: number
}
export interface TypologyAnalyticsResponse {
  typologies: TypologyStat[]
  totals: TypologyTotals
}

/* ───────────────────────────── Sub-threshold / ambient activity [GET /activity/sub-threshold] ── */
/**
 * The 'hidden 95%': every event is scored, but only fused ≥ emit_threshold (70) surfaces as an
 * alert. This is the scored-but-not-alerted population — the detection funnel + a near-miss watchlist
 * of elevated-but-below-the-bar entities the alert queue never shows.
 */
export interface SubThresholdBand {
  label: string // watch | elevated | low
  min: number
  max: number
  count: number
}
export interface WatchlistItem {
  entity_id: EntityId
  score: number // 0–100, in the 40–69 near-miss range
  top_signal: string
  ts: IsoTimestamp
}
export interface SubThresholdResponse {
  total_scored: number
  alerted: number
  sub_threshold: number
  emit_threshold: number
  bands: SubThresholdBand[]
  watchlist: WatchlistItem[]
}

/* ───────────────────────────── Score history [FE-proposed: GET /entities/{id}/score-history] ─── */
/**
 * [FE-proposed] A 0–100 fused-risk-score time series for an entity, so AlertDetail can plot how the
 * entity's risk evolved into the current alert (severity bands as ReferenceAreas). Swap to the real
 * route when BACKEND specifies it.
 */
export interface ScoreHistoryPoint {
  ts: IsoTimestamp
  score: number // 0–100 fused risk score at that timestamp
  event_id?: EventId // the L0 event that moved the score, if any
  note?: string // short human label, e.g. "new beneficiary created"
}
export interface ScoreHistoryResponse {
  entity_id: EntityId
  points: ScoreHistoryPoint[]
  /** Current decision threshold projected onto the 0–100 scale, for a reference line. */
  threshold_score?: number
}

/* ───────────────────────────── TEE attestation detail [FE-proposed: GET /narratives/{id}/attestation] ─ */
/**
 * [FE-proposed] Per-request TEE attestation record (Part 25). Lazily fetched by ProvenanceBadge only
 * when a narrative reports `tee_attested`. Mirrors the fields a TDX / confidential-inference gateway
 * returns and stores for audit; honest degradation renders without this when not attested.
 */
export interface AttestationDetail {
  alert_id: AlertId
  tee_attested: boolean
  provider: NarrativeProvider | string // e.g. "near_ai"
  gateway?: string // e.g. "near-ai-confidential-1"
  model: string // e.g. "openai/gpt-oss-120b"
  signing_address?: string // on-chain / enclave signing key
  signing_algo?: string // e.g. "secp256k1" / "ed25519"
  intel_quote_sha256?: string // SHA-256 of the Intel TDX quote
  attestation_id?: string | null
  verified_ts?: IsoTimestamp
  /** Extra provenance rows the gateway may include (rendered as-is in the KeyValueGrid). */
  extra?: { label: string; value: string }[]
}

/* ───────────────────────────── Narrative memo [BACKEND.md §7 / Part 25] ───────────────────── */
export type NarrativeProvider = 'near_ai' | 'groq' | 'template'
export interface NarrativeMemo {
  alert_id: AlertId
  /** Rendered narrative body (markdown-ish plain text). Always present — template fallback guarantees it. */
  narrative: string
  // [FE-proposed] optional structured sections the gateway may also return.
  what_happened?: string
  why_flagged?: string
  what_to_check?: string
  // Audit/provenance columns [BACKEND.md §7] — render the badge + provider.
  provider: NarrativeProvider
  tee_attested: boolean
  attestation_id?: string | null
  model: string
  prompt_hash: string
  ts: IsoTimestamp
}

/* ───────────────────────────── Graph / link view [BACKEND.md §3 / Part 24.5 + 11] ─────────── */
/** [FE-proposed] GET /entities/{id}/graph */
export type GraphNodeType =
  | 'employee'
  | 'customer'
  | 'beneficiary'
  | 'account'
  | 'device'
  | 'ip'
  | 'phone'
  | 'address'
  | 'system'
export type GraphEdgeType =
  | 'maker_checker'
  | 'shared_device'
  | 'shared_ip'
  | 'shared_phone'
  | 'shared_address'
  | 'beneficiary'
  | 'circular_flow'
  | 'mule'
  | 'transaction'

export interface GraphNode {
  id: string
  type: GraphNodeType
  label: string // tokenized id unless unmasked
  risk?: number
  is_focus?: boolean // the entity the subgraph is centred on
  tokenized?: boolean
}
export interface GraphEdge {
  id: string
  source: string
  target: string
  type: GraphEdgeType
  label?: string
  weight?: number
  ring_id?: RingId
  collusion?: boolean // maker-checker collusion highlight
  amount_inr?: number
}
export interface GraphRing {
  ring_id: RingId
  member_ids: string[]
  motif?: string // e.g. "isolated maker-checker pair"
}
export interface GraphExplainer {
  model?: string // "GNNExplainer"
  node_ids: string[]
  edge_ids: string[]
}
export interface GraphResponse {
  entity_id: EntityId
  nodes: GraphNode[]
  edges: GraphEdge[]
  rings?: GraphRing[]
  explainer?: GraphExplainer
}

/**
 * [FE-proposed] GET /graph — a global, non-entity-centred subgraph for the Graph Explorer. Reuses
 * the same node/edge encoding as the entity subgraph (so one canvas renders both); `entity_id` is a
 * synthetic overview marker rather than a focus entity. Swaps to the real `/graph` route later.
 */
export interface GraphOverviewResponse extends GraphResponse {
  min_score?: number
}

/* ───────────────────────────── Peer comparison [BACKEND.md §3 / Part 11 + 24.4] ───────────── */
/** [FE-proposed] GET /entities/{id}/peers */
export interface PeerDistribution {
  min: number
  p25: number
  median: number
  p75: number
  max: number
  mean: number
  stddev?: number
  samples?: number[] // for a jittered scatter/violin overlay
}
export interface PeerDimension {
  key: string
  label: string
  unit?: string
  actor_value: number
  peer_distribution: PeerDistribution
  z_score?: number
  flagged?: boolean
  direction?: 'higher_is_riskier' | 'lower_is_riskier'
  description?: string
}
export interface PeerComparisonResponse {
  entity_id: EntityId
  peer_group: string
  peer_count?: number
  dimensions: PeerDimension[]
}

/* ───────────────────────────── EDD / disposition [BACKEND.md §5 / Part 24.5c] ─────────────── */
export type DispositionOutcome = 'fraud' | 'false_positive' | 'inconclusive'
export interface DispositionRequest {
  outcome: DispositionOutcome
  notes: string
  evidence_ids: EventId[]
}
export interface DispositionResponse {
  alert_id: AlertId
  status: AlertStatus
  label_written: boolean
  feedback_queued_for_retraining: boolean
  audit_id: AuditId
}

/** [FE-proposed] POST /alerts/{id}/block-request — a *request*, never an auto-block. */
export interface BlockRequestBody {
  reason: string
  notes?: string
}
export interface BlockRequestResponse {
  alert_id: AlertId
  request_id: string
  status: 'pending_lead_approval'
  routed_to_role: 'team_lead'
  audit_id: AuditId
}

/** [FE-proposed] POST /alerts/{id}/assign */
export interface AssignBody {
  assignee: string
}
export interface AssignResponse {
  alert_id: AlertId
  assignee: string
  status: AlertStatus
  audit_id: AuditId
}

/** [FE-proposed] POST /feedback — active-learning label submission (Part 10 relabel loop). */
export interface FeedbackBody {
  alert_id: AlertId
  outcome: DispositionOutcome
  notes?: string
}
export interface FeedbackResponse {
  feedback_id: string
  queued_for_retraining: boolean
  audit_id: AuditId
}

/* ───────────────────────────── PII unmask [BACKEND.md §3 / Part 25.3] ─────────────────────── */
/**
 * POST /entities/{id}/unmask — audited re-identification (Senior+). Live backend body:
 * `{ tokens?: string[]; justification?: string }` (empty tokens = resolve all on the entity;
 * `justification` is required for the Relationship Manager, case-scoped + logged).
 */
export interface UnmaskBody {
  tokens?: string[]
  justification?: string
  // [FE-proposed / legacy] retained optionally; the live route reads tokens + justification.
  field?: string
  reason?: string
  alert_id?: AlertId // case-scoped for Analyst
}
export interface UnmaskResponse {
  entity_id: EntityId
  /**
   * Live backend shape: `token → re-identified value` for every token resolved by this call
   * (empty tokens list = all tokens on the entity). Read this, not a single `value`. Optional so the
   * older single-value MSW shape still type-checks; consumers must handle either.
   */
  mapping?: Record<string, string>
  audit_id: AuditId
  // [FE-proposed / MSW] legacy single-value fields kept optional for backward compatibility.
  token?: string
  value?: string
  field?: string
  audited?: boolean
}

/* ───────────────────────────── Cases [BACKEND.md §3 / Part 24.4 screen 4] ─────────────────── */
/** [FE-proposed] case store (Postgres, DATABASE) surfaced via BACKEND. */
export type CaseStatus = 'open' | 'in_progress' | 'escalated' | 'closed'
export interface CaseNote {
  id: string
  author: string
  author_role?: Role
  ts: IsoTimestamp
  body: string
}
export interface CaseHistoryEvent {
  id: string
  ts: IsoTimestamp
  actor: string
  actor_role?: Role
  action: string
  detail?: string
}
export interface CaseSummary {
  case_id: string
  title: string
  entity_id: EntityId
  status: CaseStatus
  severity: Severity
  assignee?: string | null
  alert_ids: AlertId[]
  created_ts: IsoTimestamp
  updated_ts: IsoTimestamp
  sla_due_ts?: IsoTimestamp
  exposure_inr?: number
}
export interface CaseDetail extends CaseSummary {
  alerts: Alert[]
  notes: CaseNote[]
  history: CaseHistoryEvent[]
}

/* ───────────────────────────── Rules [BACKEND.md §3 / Part 24.4 screen 5] ─────────────────── */
/** [FE-proposed] GET/POST/PUT /rules — change-controlled; four-eyes enforced server-side. */
export type RuleStatus = 'active' | 'pending_approval' | 'rejected' | 'draft' | 'disabled'
export type RuleType = 'threshold' | 'sod' | 'typology' | 'velocity'
export interface RuleParam {
  key: string
  label: string
  value: number | string | boolean
  unit?: string
}
export interface RuleChange {
  version: number
  status: RuleStatus
  proposed_by: string
  proposed_role?: Role
  approved_by?: string | null
  ts: IsoTimestamp
  summary: string
  diff?: { field: string; from: string | number | boolean; to: string | number | boolean }[]
}
export interface Rule {
  id: string
  name: string
  code?: string
  description: string
  type: RuleType
  enabled: boolean
  status: RuleStatus
  version: number
  params: RuleParam[]
  updated_by: string
  updated_ts: IsoTimestamp
  history?: RuleChange[]
}

/* ───────────────────────────── EWS / RFA coverage [Part 24.4 screen 5] ────────────────────── */
/** [FE-proposed] GET /reports/ews-coverage — early-warning / red-flag indicator coverage map. */
export interface CoverageIndicator {
  code: string
  label: string
  category: 'EWS' | 'RFA'
  covered: boolean
  source_layer?: ContributingLayer | string
  rule_id?: string
  note?: string
}
export interface EwsCoverageResponse {
  generated_ts: IsoTimestamp
  indicators: CoverageIndicator[]
  covered: number
  total: number
}

/* ───────────────────────────── Regulatory exports [BACKEND.md §3 / Part 24.4] ─────────────── */
export type ReportType = 'fmr' | 'crilc'
export interface ReportLineItem {
  ref: string
  entity_id?: EntityId
  alert_id?: AlertId
  amount_inr?: number
  category?: string
  detail?: string
}
export interface ReportExport {
  report_id: string
  type: ReportType
  status: 'ready' | 'generating'
  generated_ts: IsoTimestamp
  period?: { from: IsoTimestamp; to: IsoTimestamp }
  summary: string
  line_items: ReportLineItem[]
  /** Mock download payload (CSV-ish text) so the UI can offer a one-click download. */
  download_filename?: string
  download_content?: string
}

/* ───────────────────────────── Models / drift — LIVE backend shapes ────────────────────────── */
/**
 * Raw registry row from the live `GET /models` (serving registry). Note the capitalised `stage`
 * ("Production" / "Challenger" / "Staging" / "Archived"), the `model_id` (no `id`/`name`/`created_ts`),
 * and a free-form `metrics` bag whose keys vary by layer (pr_auc, precision_at_k, vus_pr, …).
 */
export interface RawModelInfo {
  model_id: string
  layer: string
  version: string
  stage: string
  signed: boolean
  training_data_hash?: string
  feature_set_version?: string
  approving_reviewer?: string | null
  metrics?: Record<string, number> | null
}
/** Raw flat `GET /drift` report for one model. */
export interface RawDriftReport {
  model_id: string
  version?: string
  data_drift_psi: number
  concept_drift: number
  drift_crossed: boolean
  window?: string
}
/** Raw flat `GET /metrics/model` quality snapshot for one model. */
export interface RawModelQuality {
  model_id: string
  version?: string
  pr_auc?: number | null
  precision_at_k?: number | null
  alert_to_true_fraud_ratio?: number | null
  calibration_error?: number | null
}
/** Live `POST /models/{id}/promote?version=…` request body. */
export interface PromoteRequestBody {
  to_stage: string
  signoff_by: string
  canary_percent?: number
}
/** Live `POST /models/{id}/promote` result. */
export interface RawPromoteResult {
  model_id: string
  version: string
  stage: string
  canary_percent: number
  signature_verified: boolean
  audit_id: AuditId
}

/* ───────────────────────────── Models / drift [BACKEND.md §3 / Part 24.4 screen 7] ────────── */
/** [FE-proposed] GET /models, POST /models/{id}/promote, GET /drift, GET /metrics/model. */
export type ModelStage = 'champion' | 'challenger' | 'staging' | 'archived'
export interface ModelMetrics {
  auc?: number
  pr_auc?: number
  precision?: number
  recall?: number
  f1?: number
  fpr?: number
  brier?: number
  // Additional live-registry metrics (vary by layer); surfaced where a column exists.
  precision_at_k?: number
  vus_pr?: number
  calibration_error?: number
  alert_to_true_fraud_ratio?: number
}
export interface ModelEntry {
  id: string
  name: string
  layer: ContributingLayer | string
  version: string
  stage: ModelStage
  signed: boolean
  promoted_by?: string | null
  created_ts: IsoTimestamp
  metrics?: ModelMetrics
  de_identified: true // matrix: model-engineer sees de-identified data only
}
export interface ModelPromoteResponse {
  model_id: string
  stage: ModelStage
  requires_signoff: boolean
  audit_id: AuditId
}
export type DriftStatus = 'ok' | 'warning' | 'drifting'
export interface DriftPoint {
  ts: IsoTimestamp
  value: number
  threshold?: number
}
export interface DriftSeries {
  model_id: string
  feature?: string
  metric: 'psi' | 'ks' | 'js'
  status: DriftStatus
  points: DriftPoint[]
}
export interface DriftResponse {
  generated_ts: IsoTimestamp
  series: DriftSeries[]
}
export interface ModelQualityPoint {
  ts: IsoTimestamp
  metric: string
  value: number
}
export interface ModelQualityResponse {
  models: { model_id: string; metrics: ModelMetrics; trend?: ModelQualityPoint[] }[]
}

/* ───────────────────────────── Audit [BACKEND.md §3 / Part 24.4 screen 6] ─────────────────── */
/** [FE-proposed] GET /audit — immutable WORM trail incl. who-viewed-whom. */
export interface AuditEvent {
  audit_id: AuditId
  ts: IsoTimestamp
  actor: string
  actor_role?: Role | string
  // Live backend uses a dotted vocabulary: alert.view / pii.unmask / alert.disposition /
  // narrative.generate / model.promote / rule.change_* / admin.user_create / audit.view …
  action: string
  entity_id?: EntityId | null
  alert_id?: AlertId | null
  target?: string | null
  outcome?: string | null
  src_ip?: string | null
  /**
   * Free-form structured context for the entry. The live `/audit` route returns this as an OBJECT
   * (e.g. `{ alert_id, outcome, evidence_ids }`), older/[FE-proposed] shapes used a string. Render
   * defensively — never as a raw React child.
   */
  detail?: Record<string, unknown> | string | null
}
export interface AuditQuery {
  actor?: string
  entity?: string
  from?: string
  to?: string
  action?: string
  page?: number
  page_size?: number
}

/* ───────────────────────────── Admin [BACKEND.md §3 / Part 24.4 screen 8] ─────────────────── */
export interface AdminUser {
  id: string
  username: string
  display_name: string
  email?: string
  roles: Role[]
  status: 'active' | 'disabled'
  created_ts: IsoTimestamp
  last_login?: IsoTimestamp | null
}
export interface CreateUserBody {
  username: string
  display_name: string
  email?: string
  roles: Role[]
}

/* ───────────────────────────── Health / metrics [BACKEND.md §3] ───────────────────────────── */
export interface ServiceHealth {
  name: string
  status: 'ok' | 'degraded' | 'down'
  latency_ms?: number
  detail?: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down'
  version?: string
  services: ServiceHealth[]
  checked_ts: IsoTimestamp
}

/* ───────────────────────────── Service map [BACKEND: GET /services/status] ─────────────────── */
/**
 * Live platform service-catalogue row surfaced by `GET /services/status` (Agent B's shape). Powers
 * the Admin Service Map: what each service is, WHERE in the app it's used, and its live status.
 *
 * `status` is honest about the deployment reality:
 *  - `up`         — a real client is configured and the service answered its probe.
 *  - `in_process` — the capability is served by an in-process runtime / fallback (no external dep).
 *  - `optional`   — not wired for this deployment; the app runs without it (in-memory / default mode).
 *  - `down`       — a real client is configured but the service failed its probe (honest degradation).
 *  - `unknown`    — status could not be determined (probe not run / shape surprise).
 */
export type ServiceStatusState = 'up' | 'in_process' | 'optional' | 'down' | 'unknown'
export interface ServiceStatus {
  key: string
  name: string
  purpose: string
  /** Where in Hawk-Eye this service is used (feature / module), for the "used by" line. */
  used_by: string
  required: boolean
  /** Rationale surfaced as a tooltip when the service is optional (why it's safe to run without). */
  why?: string
  status: ServiceStatusState
  /** Optional probe detail (e.g. resolved endpoint, latency, fallback note). */
  detail?: string
  latency_ms?: number
}
export interface ServiceStatusResponse {
  generated_ts: IsoTimestamp
  services: ServiceStatus[]
}
/**
 * Raw live `GET /health` — served at the server ROOT (not under `/api/v1`) as a flat status dict.
 * Adapted (apiClient.getHealth) into the {services[]} render shape the health panel expects.
 */
export interface RawHealth {
  status: string
  service?: string
  version?: string
  env?: string
  serving_ready?: boolean
  degraded_l1_only?: boolean
  mtls_internal?: boolean
  auth_mode?: string
  alert_only?: boolean
  pii?: Record<string, unknown>
  [k: string]: unknown
}

/* ───────────────────────────── Reporting / KRIs [Part 24.4 / Part 11 reporting] ───────────── */
/** [FE-proposed] GET /reports/kris — management + board (SCBMF) KRI dashboard. */
export interface KriCard {
  key: string
  label: string
  value: number
  unit?: string
  target?: number
  direction?: 'higher_is_better' | 'lower_is_better'
  status?: 'ok' | 'warning' | 'breach'
  delta?: number // vs previous period
}
export interface KriTrendPoint {
  period: string // e.g. "2026-W26" or ISO date
  [series: string]: number | string
}
export interface CoverageCell {
  area: string // typology / unit / branch
  covered_pct: number
}
export interface KriResponse {
  generated_ts: IsoTimestamp
  cards: KriCard[]
  trends: KriTrendPoint[]
  coverage: CoverageCell[]
}

/* ───────────────────────────── Auth [BACKEND.md §3 / Part 24.1] ───────────────────────────── */
export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: 'Bearer'
  expires_in: number // seconds
}
export interface AuthUser {
  sub: string
  username: string
  name: string
  email?: string
  roles: Role[]
}

/* ── M2.1 — continuous per-user insider-risk index ─────────────────────────── */
export interface RiskIndexComponent {
  name: string
  group: string // "hr" | "access" | "anomaly"
  value: number // 0–1
  detail: string
}
export interface RiskIndex {
  employee_id: string
  composite: number // 0–100
  hr_score: number // 0–1
  access_score: number // 0–1
  anomaly_score: number // 0–1
  components: RiskIndexComponent[]
  top_drivers: string[]
  updated_ts?: string | null
  calibrated: boolean // false = stub weights (human review only, never auto-actioned)
}
