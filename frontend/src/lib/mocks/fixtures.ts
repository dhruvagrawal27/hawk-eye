/**
 * MSW fixtures — synthetic, on-prem-only data (golden rule #2). The centrepiece is the **Part 24.5
 * worked burst** rendered byte-for-byte (alert `alr_3d7e22`, entity `EMP-7f3a`, ring `RNG-12`,
 * exposure ₹48,00,000, SLA 2026-07-30) so the triage queue, alert detail, explanation, graph and
 * disposition all show the canonical example. Everything else is variety so each screen looks real:
 * multiple entities, all severities/statuses, every SLA band, dedup groups, four-eyes rule changes,
 * champion/challenger models, drift, audit (who-viewed-whom), KRIs and regulatory exports.
 *
 * Timestamps are anchored to the blueprint epoch (2026-06-30, "today" per the brief) and are static
 * so contract tests are deterministic. IDs follow CONTEXT.md §6 (evt_/alr_/EMP-/RNG-/aud_/ACCT-/BEN-).
 */
import type {
  AdminUser,
  Alert,
  AuditEvent,
  CaseDetail,
  CaseSummary,
  DriftResponse,
  EntityProfile,
  EwsCoverageResponse,
  ExplanationResponse,
  GraphResponse,
  HealthResponse,
  KriResponse,
  ModelEntry,
  ModelQualityResponse,
  NarrativeMemo,
  PeerComparisonResponse,
  ReportExport,
  Rule,
  SubThresholdResponse,
  TimelineResponse,
  UnifiedEvent,
  UnmaskResponse,
} from '../types'

/* ───────────────────────────── The canonical sample event [Part 24.5a] ─────────────────────── */
export const SAMPLE_EVENT: UnifiedEvent = {
  event_id: 'evt_8f2a1c90',
  ts: '2026-06-30T02:14:07Z',
  actor: {
    employee_id: 'EMP-7f3a',
    role: 'ops_maker',
    dept: 'trade_finance',
    branch: 'BR-219',
    tenure_days: 2840,
    peer_group: 'PG-ops-tf',
    privileged_flag: false,
    leaver_flag: false,
  },
  action: { verb: 'create_beneficiary', channel: 'cbs', maker_checker: 'maker' },
  object: { beneficiary_id: 'BEN-9b1c', account_id: 'ACCT-4d22', amount: null, currency: 'INR' },
  context: {
    src_ip: '10.20.4.31',
    device: 'WS-114',
    geo: 'Mumbai',
    session_id: 'sess_55e1',
    layer: 'application',
    is_off_hours: true,
  },
}

/* ───────────────────────────── The canonical sample alert [Part 24.5b] ──────────────────────── */
export const SAMPLE_ALERT: Alert = {
  alert_id: 'alr_3d7e22',
  entity_id: 'EMP-7f3a',
  risk_score: 87,
  severity: 'high',
  confidence: 0.82,
  status: 'open',
  created_ts: '2026-06-30T02:41:55Z',
  contributing_layers: ['L1_rules', 'L2_unsupervised', 'L3_gbdt', 'L5_graph'],
  reason_codes: [
    {
      source: 'rule',
      code: 'NEW_BENEFICIARY_THEN_HIGHVALUE',
      detail: 'new payee BEN-9b1c paid INR 48,00,000 within 27 min',
    },
    {
      source: 'rule',
      code: 'OFF_HOURS_ACTIVITY',
      detail: '02:14 IST, outside actor & peer baseline',
    },
    { source: 'shap', feature: 'new_beneficiary_to_payment_latency_min', contribution: 0.31 },
    { source: 'shap', feature: 'maker_checker_pair_frequency_30d', contribution: 0.22 },
    {
      source: 'graph',
      detail: 'maker EMP-7f3a + checker EMP-1a09 recur as an isolated pair (ring_id RNG-12)',
      ring_id: 'RNG-12',
    },
  ],
  exposure_inr: 4800000,
  sla_due_ts: '2026-07-30T02:41:55Z',
  pii_tokenized: true,
  assignee: null,
  alert_type: 'maker_checker_collusion',
  title: 'New-beneficiary high-value payout with off-hours maker-checker pairing',
}

/* ───────────────────────────── Entities ────────────────────────────────────────────────────── */
function entity(
  p: Partial<EntityProfile> &
    Pick<EntityProfile, 'entity_id' | 'role' | 'dept' | 'branch' | 'peer_group' | 'risk_score'>,
): EntityProfile {
  return {
    employee_id: p.entity_id,
    display_name: p.entity_id,
    tenure_days: 1500,
    privileged_flag: false,
    leaver_flag: false,
    pii_tokenized: true,
    status: 'active',
    ...p,
  }
}

export const ENTITIES: Record<string, EntityProfile> = {
  'EMP-7f3a': entity({
    entity_id: 'EMP-7f3a',
    role: 'ops_maker',
    dept: 'trade_finance',
    branch: 'BR-219',
    peer_group: 'PG-ops-tf',
    tenure_days: 2840,
    risk_score: 87,
    manager_id: 'EMP-0a01',
    open_alert_count: 3,
  }),
  'EMP-1a09': entity({
    entity_id: 'EMP-1a09',
    role: 'ops_checker',
    dept: 'trade_finance',
    branch: 'BR-219',
    peer_group: 'PG-ops-tf',
    tenure_days: 3120,
    risk_score: 78,
    open_alert_count: 1,
  }),
  'EMP-3c55': entity({
    entity_id: 'EMP-3c55',
    role: 'database_admin',
    dept: 'it_operations',
    branch: 'BR-001',
    peer_group: 'PG-it-dba',
    tenure_days: 1980,
    privileged_flag: true,
    risk_score: 72,
    open_alert_count: 2,
  }),
  'EMP-9d20': entity({
    entity_id: 'EMP-9d20',
    role: 'teller',
    dept: 'retail_banking',
    branch: 'BR-118',
    peer_group: 'PG-retail-teller',
    tenure_days: 410,
    leaver_flag: true,
    risk_score: 81,
    open_alert_count: 2,
  }),
  'EMP-2b88': entity({
    entity_id: 'EMP-2b88',
    role: 'loan_officer',
    dept: 'credit',
    branch: 'BR-044',
    peer_group: 'PG-credit-lo',
    tenure_days: 2210,
    risk_score: 64,
    open_alert_count: 2,
  }),
  'EMP-5e11': entity({
    entity_id: 'EMP-5e11',
    role: 'treasury_dealer',
    dept: 'treasury',
    branch: 'BR-001',
    peer_group: 'PG-treasury',
    tenure_days: 1670,
    risk_score: 69,
    open_alert_count: 2,
  }),
  'EMP-6a02': entity({
    entity_id: 'EMP-6a02',
    role: 'payroll_admin',
    dept: 'human_resources',
    branch: 'BR-001',
    peer_group: 'PG-hr-payroll',
    tenure_days: 990,
    privileged_flag: true,
    risk_score: 58,
    open_alert_count: 1,
  }),
  'EMP-8f44': entity({
    entity_id: 'EMP-8f44',
    role: 'branch_ops',
    dept: 'retail_banking',
    branch: 'BR-077',
    peer_group: 'PG-retail-ops',
    tenure_days: 760,
    risk_score: 75,
    open_alert_count: 1,
  }),
}

/* ───────────────────────────── Alerts (queue) ──────────────────────────────────────────────── */
function alert(
  p: Partial<Alert> &
    Pick<
      Alert,
      | 'alert_id'
      | 'entity_id'
      | 'risk_score'
      | 'severity'
      | 'confidence'
      | 'status'
      | 'exposure_inr'
      | 'sla_due_ts'
    >,
): Alert {
  return {
    created_ts: '2026-06-30T02:41:55Z',
    contributing_layers: ['L1_rules', 'L3_gbdt'],
    reason_codes: [],
    pii_tokenized: true,
    assignee: null,
    ...p,
  }
}

export const ALERTS: Alert[] = [
  SAMPLE_ALERT,
  // dedup group for EMP-7f3a (2 more)
  alert({
    alert_id: 'alr_7c12',
    entity_id: 'EMP-7f3a',
    risk_score: 74,
    severity: 'high',
    confidence: 0.71,
    status: 'open',
    exposure_inr: 1200000,
    sla_due_ts: '2026-07-04T09:00:00Z',
    created_ts: '2026-06-29T19:22:00Z',
    contributing_layers: ['L1_rules', 'L3_gbdt'],
    alert_type: 'rapid_payout',
    title: 'Repeat new-beneficiary payout pattern',
    reason_codes: [
      {
        source: 'rule',
        code: 'NEW_BENEFICIARY_THEN_HIGHVALUE',
        detail: 'payee BEN-2c7d paid INR 12,00,000 within 41 min',
      },
      { source: 'shap', feature: 'new_beneficiary_to_payment_latency_min', contribution: 0.24 },
    ],
  }),
  alert({
    alert_id: 'alr_9a55',
    entity_id: 'EMP-7f3a',
    risk_score: 61,
    severity: 'medium',
    confidence: 0.6,
    status: 'assigned',
    assignee: 'rm.demo',
    exposure_inr: 300000,
    sla_due_ts: '2026-07-12T09:00:00Z',
    created_ts: '2026-06-28T11:05:00Z',
    contributing_layers: ['L2_unsupervised'],
    alert_type: 'off_hours',
    title: 'Off-hours access spike',
    reason_codes: [
      {
        source: 'rule',
        code: 'OFF_HOURS_ACTIVITY',
        detail: 'three logins between 01:00–03:00 IST',
      },
    ],
  }),
  alert({
    alert_id: 'alr_4d88',
    entity_id: 'EMP-1a09',
    risk_score: 78,
    severity: 'high',
    confidence: 0.77,
    status: 'open',
    exposure_inr: 4800000,
    sla_due_ts: '2026-07-02T02:41:55Z',
    created_ts: '2026-06-30T02:42:10Z',
    contributing_layers: ['L1_rules', 'L5_graph'],
    alert_type: 'maker_checker_collusion',
    title: 'Checker side of isolated maker-checker pair',
    reason_codes: [
      {
        source: 'graph',
        detail: 'checker EMP-1a09 approves only maker EMP-7f3a (ring RNG-12)',
        ring_id: 'RNG-12',
      },
      { source: 'shap', feature: 'maker_checker_pair_frequency_30d', contribution: 0.27 },
    ],
  }),
  alert({
    alert_id: 'alr_2f31',
    entity_id: 'EMP-3c55',
    risk_score: 72,
    severity: 'high',
    confidence: 0.69,
    status: 'escalated',
    exposure_inr: 2500000,
    sla_due_ts: '2026-06-28T18:00:00Z', // breached
    created_ts: '2026-06-27T22:14:00Z',
    contributing_layers: ['L1_rules', 'L2_unsupervised', 'L3_gbdt'],
    alert_type: 'data_exfiltration',
    title: 'DBA bulk customer-table read off-hours',
    reason_codes: [
      {
        source: 'rule',
        code: 'BULK_DATA_READ',
        detail: '41k customer rows exported via ad-hoc query at 23:48 IST',
      },
      { source: 'shap', feature: 'rows_read_zscore_vs_peer', contribution: 0.34 },
    ],
  }),
  alert({
    alert_id: 'alr_0d19',
    entity_id: 'EMP-3c55',
    risk_score: 66,
    severity: 'medium',
    confidence: 0.62,
    status: 'open',
    exposure_inr: 1000000,
    sla_due_ts: '2026-07-06T09:00:00Z',
    created_ts: '2026-06-29T08:30:00Z',
    contributing_layers: ['L1_rules'],
    alert_type: 'privilege_self_grant',
    title: 'Privileged role self-granted without ticket',
    reason_codes: [
      {
        source: 'rule',
        code: 'PRIVILEGE_SELF_GRANT',
        detail: 'db_admin role added by same actor, no change ticket',
      },
    ],
  }),
  alert({
    alert_id: 'alr_6b07',
    entity_id: 'EMP-9d20',
    risk_score: 81,
    severity: 'high',
    confidence: 0.8,
    status: 'open',
    exposure_inr: 1500000,
    sla_due_ts: '2026-07-01T09:00:00Z', // urgent
    created_ts: '2026-06-29T20:01:00Z',
    contributing_layers: ['L1_rules', 'L3_gbdt', 'L4_sequence'],
    alert_type: 'leaver_exfiltration',
    title: 'Resigning teller bulk-downloads before last day',
    reason_codes: [
      {
        source: 'rule',
        code: 'LEAVER_BULK_ACCESS',
        detail: 'leaver flag set; 1,240 statements exported in 2 days',
      },
      { source: 'shap', feature: 'export_volume_vs_baseline', contribution: 0.29 },
    ],
  }),
  alert({
    alert_id: 'alr_a7e3',
    entity_id: 'EMP-9d20',
    risk_score: 52,
    severity: 'medium',
    confidence: 0.5,
    status: 'inconclusive',
    exposure_inr: 250000,
    sla_due_ts: '2026-07-15T09:00:00Z',
    created_ts: '2026-06-25T14:00:00Z',
    contributing_layers: ['L2_unsupervised'],
    alert_type: 'off_hours',
    title: 'Minor after-hours access anomaly',
    reason_codes: [{ source: 'shap', feature: 'off_hours_activity_rate_30d', contribution: 0.14 }],
  }),
  alert({
    alert_id: 'alr_1e90',
    entity_id: 'EMP-2b88',
    risk_score: 64,
    severity: 'medium',
    confidence: 0.58,
    status: 'open',
    exposure_inr: 7500000,
    sla_due_ts: '2026-07-18T09:00:00Z',
    created_ts: '2026-06-26T10:12:00Z',
    contributing_layers: ['L1_rules', 'L3_gbdt'],
    alert_type: 'ghost_loan',
    title: 'Loan appraised & disbursed to thin-file borrower',
    reason_codes: [
      {
        source: 'rule',
        code: 'SELF_APPRAISAL_DISBURSAL',
        detail: 'same officer appraised and released INR 75,00,000',
      },
      { source: 'shap', feature: 'borrower_file_completeness', contribution: 0.21 },
    ],
  }),
  alert({
    alert_id: 'alr_b2a1',
    entity_id: 'EMP-2b88',
    risk_score: 45,
    severity: 'low',
    confidence: 0.4,
    status: 'false_positive',
    exposure_inr: 180000,
    sla_due_ts: '2026-07-20T09:00:00Z',
    created_ts: '2026-06-20T09:00:00Z',
    contributing_layers: ['L2_unsupervised'],
    alert_type: 'amount_anomaly',
    title: 'Amount anomaly — cleared as seasonal',
    reason_codes: [{ source: 'shap', feature: 'amount_zscore_vs_peer', contribution: 0.11 }],
  }),
  alert({
    alert_id: 'alr_8c23',
    entity_id: 'EMP-5e11',
    risk_score: 69,
    severity: 'high',
    confidence: 0.66,
    status: 'in_progress',
    assignee: 'branch.demo',
    exposure_inr: 22000000,
    sla_due_ts: '2026-07-09T09:00:00Z',
    created_ts: '2026-06-28T05:40:00Z',
    contributing_layers: ['L1_rules', 'L3_gbdt', 'L4_sequence'],
    alert_type: 'rogue_trading',
    title: 'Limit breach with delayed booking',
    reason_codes: [
      {
        source: 'rule',
        code: 'LIMIT_BREACH_DELAYED_BOOKING',
        detail: 'position exceeded desk limit; booking delayed 6h',
      },
      { source: 'shap', feature: 'booking_latency_min', contribution: 0.26 },
    ],
  }),
  alert({
    alert_id: 'alr_c4d2',
    entity_id: 'EMP-5e11',
    risk_score: 91,
    severity: 'critical',
    confidence: 0.88,
    status: 'confirmed_fraud',
    exposure_inr: 31000000,
    sla_due_ts: '2026-07-05T09:00:00Z',
    created_ts: '2026-06-18T05:40:00Z',
    contributing_layers: ['L1_rules', 'L3_gbdt', 'L5_graph'],
    alert_type: 'rogue_trading',
    title: 'Confirmed unauthorised position (closed)',
    reason_codes: [
      {
        source: 'rule',
        code: 'UNAUTHORISED_INSTRUMENT',
        detail: 'trades in non-mandated instrument',
      },
    ],
  }),
  alert({
    alert_id: 'alr_3a47',
    entity_id: 'EMP-6a02',
    risk_score: 58,
    severity: 'medium',
    confidence: 0.55,
    status: 'open',
    exposure_inr: 950000,
    sla_due_ts: '2026-07-25T09:00:00Z',
    created_ts: '2026-06-24T07:00:00Z',
    contributing_layers: ['L1_rules', 'L5_graph'],
    alert_type: 'ghost_employee',
    title: 'Payroll to account sharing device with admin',
    reason_codes: [
      { source: 'graph', detail: 'payee account shares device WS-330 with payroll admin EMP-6a02' },
      {
        source: 'rule',
        code: 'NEW_EMPLOYEE_RAPID_PAYROLL',
        detail: 'employee created and paid within one cycle',
      },
    ],
  }),
  alert({
    alert_id: 'alr_5f70',
    entity_id: 'EMP-8f44',
    risk_score: 75,
    severity: 'high',
    confidence: 0.73,
    status: 'open',
    exposure_inr: 3200000,
    sla_due_ts: '2026-07-04T09:00:00Z',
    created_ts: '2026-06-29T16:45:00Z',
    contributing_layers: ['L1_rules', 'L2_unsupervised', 'L3_gbdt'],
    alert_type: 'dormant_takeover',
    title: 'Dormant account reactivated then drained',
    reason_codes: [
      {
        source: 'rule',
        code: 'DORMANT_REACTIVATION_THEN_DEBIT',
        detail: 'dormant 18m, reactivated and debited INR 32,00,000',
      },
      { source: 'shap', feature: 'days_since_last_activity', contribution: 0.3 },
    ],
  }),
]

export function findAlert(id: string): Alert | undefined {
  return ALERTS.find((a) => a.alert_id === id)
}

/* ───────────────────────────── Entity-360 timeline (EMP-7f3a) [Part 24.5a shape] ───────────── */
function ev(
  p: Partial<UnifiedEvent> &
    Pick<UnifiedEvent, 'event_id' | 'ts'> & {
      verb: string
      channel: string
      layer: string
      maker_checker?: 'maker' | 'checker' | null
      off?: boolean
      amount?: number | null
      beneficiary_id?: string | null
      account_id?: string | null
    },
): UnifiedEvent {
  return {
    event_id: p.event_id,
    ts: p.ts,
    actor: {
      employee_id: 'EMP-7f3a',
      role: 'ops_maker',
      dept: 'trade_finance',
      branch: 'BR-219',
      tenure_days: 2840,
      peer_group: 'PG-ops-tf',
      privileged_flag: false,
      leaver_flag: false,
    },
    action: { verb: p.verb, channel: p.channel, maker_checker: p.maker_checker ?? null },
    object: {
      beneficiary_id: p.beneficiary_id ?? null,
      account_id: p.account_id ?? null,
      amount: p.amount ?? null,
      currency: 'INR',
    },
    context: {
      src_ip: '10.20.4.31',
      device: 'WS-114',
      geo: 'Mumbai',
      session_id: 'sess_55e1',
      layer: p.layer,
      is_off_hours: p.off ?? false,
    },
  }
}

export const TIMELINES: Record<string, TimelineResponse> = {
  'EMP-7f3a': {
    entity_id: 'EMP-7f3a',
    events: [
      ev({
        event_id: 'evt_8f2a1a40',
        ts: '2026-06-22T05:30:00Z',
        verb: 'role_review_completed',
        channel: 'hr_iga',
        layer: 'change',
      }),
      ev({
        event_id: 'evt_8f2a1a88',
        ts: '2026-06-28T04:10:00Z',
        verb: 'vpn_login',
        channel: 'iam',
        layer: 'identity',
      }),
      ev({
        event_id: 'evt_8f2a1b02',
        ts: '2026-06-29T19:40:00Z',
        verb: 'login',
        channel: 'iam',
        layer: 'identity',
        off: true,
      }),
      ev({
        event_id: 'evt_8f2a1b51',
        ts: '2026-06-29T20:05:00Z',
        verb: 'query_customer_table',
        channel: 'db_audit',
        layer: 'data',
        off: true,
      }),
      ev({
        event_id: 'evt_8f2a1c90',
        ts: '2026-06-30T02:14:07Z',
        verb: 'create_beneficiary',
        channel: 'cbs',
        layer: 'application',
        maker_checker: 'maker',
        off: true,
        beneficiary_id: 'BEN-9b1c',
        account_id: 'ACCT-4d22',
      }),
      ev({
        event_id: 'evt_8f2a1cf2',
        ts: '2026-06-30T02:26:00Z',
        verb: 'amend_beneficiary_limit',
        channel: 'cbs',
        layer: 'application',
        maker_checker: 'maker',
        off: true,
        beneficiary_id: 'BEN-9b1c',
      }),
      ev({
        event_id: 'evt_8f2a1d04',
        ts: '2026-06-30T02:33:10Z',
        verb: 'initiate_payment',
        channel: 'cbs',
        layer: 'application',
        maker_checker: 'maker',
        off: true,
        amount: 4800000,
        beneficiary_id: 'BEN-9b1c',
        account_id: 'ACCT-4d22',
      }),
      ev({
        event_id: 'evt_8f2a1d77',
        ts: '2026-06-30T02:39:00Z',
        verb: 'export_payment_advice',
        channel: 'db_audit',
        layer: 'data',
        off: true,
      }),
      ev({
        event_id: 'evt_8f2a1e10',
        ts: '2026-06-30T08:55:00Z',
        verb: 'logout',
        channel: 'iam',
        layer: 'identity',
      }),
    ],
  },
}

/* ───────────────────────────── Explanation (alr_3d7e22) ────────────────────────────────────── */
export const EXPLANATIONS: Record<string, ExplanationResponse> = {
  alr_3d7e22: {
    alert_id: 'alr_3d7e22',
    shap: [
      {
        feature: 'new_beneficiary_to_payment_latency_min',
        contribution: 0.31,
        value: 27,
        direction: 'increases_risk',
      },
      {
        feature: 'maker_checker_pair_frequency_30d',
        contribution: 0.22,
        value: 14,
        direction: 'increases_risk',
      },
      {
        feature: 'amount_zscore_vs_peer',
        contribution: 0.18,
        value: 3.4,
        direction: 'increases_risk',
      },
      {
        feature: 'off_hours_activity_rate_30d',
        contribution: 0.12,
        value: 0.41,
        direction: 'increases_risk',
      },
      {
        feature: 'beneficiary_age_days',
        contribution: -0.09,
        value: 0,
        direction: 'decreases_risk',
      },
      {
        feature: 'actor_tenure_days',
        contribution: -0.05,
        value: 2840,
        direction: 'decreases_risk',
      },
    ],
    rules: [
      {
        code: 'NEW_BENEFICIARY_THEN_HIGHVALUE',
        detail: 'New payee BEN-9b1c created then paid INR 48,00,000 within 27 minutes.',
        typology: 'Rapid payout to newly-created beneficiary',
        sod_rule: 'Maker initiated high-value payment to self-created payee',
        severity: 'high',
        layer: 'L1_rules',
      },
      {
        code: 'OFF_HOURS_ACTIVITY',
        detail: 'Activity at 02:14 IST is outside both the actor and PG-ops-tf peer baseline.',
        typology: 'Off-hours privileged action',
        severity: 'medium',
        layer: 'L1_rules',
      },
    ],
    attention: [
      {
        session_id: 'sess_55e1',
        model: 'LAXCAT',
        steps: [
          {
            event_id: 'evt_8f2a1b02',
            ts: '2026-06-29T19:40:00Z',
            label: 'login',
            weight: 0.18,
            verb: 'login',
            is_off_hours: true,
          },
          {
            event_id: 'evt_8f2a1c90',
            ts: '2026-06-30T02:14:07Z',
            label: 'create_beneficiary',
            weight: 0.74,
            verb: 'create_beneficiary',
            is_off_hours: true,
          },
          {
            event_id: 'evt_8f2a1cf2',
            ts: '2026-06-30T02:26:00Z',
            label: 'amend_beneficiary_limit',
            weight: 0.46,
            verb: 'amend_beneficiary_limit',
            is_off_hours: true,
          },
          {
            event_id: 'evt_8f2a1d04',
            ts: '2026-06-30T02:33:10Z',
            label: 'initiate_payment',
            weight: 0.93,
            verb: 'initiate_payment',
            is_off_hours: true,
          },
          {
            event_id: 'evt_8f2a1d77',
            ts: '2026-06-30T02:39:00Z',
            label: 'export_payment_advice',
            weight: 0.39,
            verb: 'export_payment_advice',
            is_off_hours: true,
          },
        ],
      },
    ],
    graph: {
      ring_id: 'RNG-12',
      summary:
        'Maker EMP-7f3a and checker EMP-1a09 recur as an isolated approval pair across 14 of the last 30 days — a closed maker-checker loop with no other counterparties.',
      explainer_model: 'GNNExplainer',
      nodes: [
        { id: 'EMP-7f3a', label: 'EMP-7f3a', type: 'employee', importance: 1 },
        { id: 'EMP-1a09', label: 'EMP-1a09', type: 'employee', importance: 0.86 },
        { id: 'BEN-9b1c', label: 'BEN-9b1c', type: 'beneficiary', importance: 0.71 },
      ],
      edges: [
        { source: 'EMP-7f3a', target: 'EMP-1a09', type: 'maker_checker', importance: 0.93 },
        { source: 'EMP-7f3a', target: 'BEN-9b1c', type: 'beneficiary', importance: 0.64 },
      ],
    },
  },
}

/* ───────────────────────────── Narratives (TEE-attested + template fallback) [Part 25] ─────── */
export const NARRATIVES: Record<string, NarrativeMemo> = {
  alr_3d7e22: {
    alert_id: 'alr_3d7e22',
    narrative:
      'At 02:14 IST on 30 Jun 2026 — outside the actor and peer baseline — maker EMP-7f3a created a new beneficiary (BEN-9b1c) and, 27 minutes later, initiated a payment of INR 48,00,000 to that payee. The approving checker, EMP-1a09, forms an isolated maker-checker pair with EMP-7f3a (ring RNG-12), having co-approved 14 times in 30 days with no other counterparties. The new-beneficiary-to-payment latency (27 min) and the maker-checker pair frequency are the strongest model drivers; the amount is 3.4σ above the peer group. Recommended checks: confirm BEN-9b1c is a genuine, independently-verified payee; review the approval trail for EMP-1a09; and verify whether the off-hours window aligns with any legitimate trade-finance settlement deadline.',
    what_happened:
      'New beneficiary created off-hours, then paid INR 48,00,000 within 27 minutes, approved by a recurring isolated checker.',
    why_flagged:
      'L1 rules (NEW_BENEFICIARY_THEN_HIGHVALUE, OFF_HOURS_ACTIVITY), L3 GBDT (latency + amount z-score), and L5 graph (ring RNG-12) all fired and fused to risk 87.',
    what_to_check:
      'Independently verify BEN-9b1c; review EMP-1a09 approval independence; check for a legitimate settlement deadline explaining the off-hours window.',
    provider: 'near_ai',
    tee_attested: true,
    attestation_id: 'att_tdx_h200_5f2c91',
    model: 'openai/gpt-oss-120b',
    prompt_hash: 'sha256:9b1c7f3a…d04e',
    ts: '2026-06-30T02:41:56Z',
  },
  // Degraded path for the narrative-degradation test: deterministic template, NOT TEE-attested.
  alr_4d88: {
    alert_id: 'alr_4d88',
    narrative:
      '[Template] Alert alr_4d88 for EMP-1a09 fired on rules and graph signals. Checker EMP-1a09 approves predominantly one maker (EMP-7f3a), forming ring RNG-12. Review approval independence and counterparty diversity.',
    provider: 'template',
    tee_attested: false,
    attestation_id: null,
    model: 'deterministic-jinja-fallback',
    prompt_hash: 'sha256:template:alr_4d88',
    ts: '2026-06-30T02:42:11Z',
  },
}

export function narrativeFor(alertId: string): NarrativeMemo {
  if (NARRATIVES[alertId]) return NARRATIVES[alertId]
  // Any other alert → deterministic template fallback (UI never breaks; tee_attested=false).
  const a = findAlert(alertId)
  return {
    alert_id: alertId,
    narrative:
      `[Template] Alert ${alertId}${a ? ` for ${a.entity_id}` : ''} was generated by the deterministic fallback. ${a?.reason_codes.map((r) => ('detail' in r ? r.detail : `${r.feature} ${r.contribution}`)).join(' ') ?? ''}`.trim(),
    provider: 'template',
    tee_attested: false,
    attestation_id: null,
    model: 'deterministic-jinja-fallback',
    prompt_hash: `sha256:template:${alertId}`,
    ts: '2026-06-30T03:00:00Z',
  }
}

/* ───────────────────────────── Graph (EMP-7f3a) ────────────────────────────────────────────── */
export const GRAPHS: Record<string, GraphResponse> = {
  'EMP-7f3a': {
    entity_id: 'EMP-7f3a',
    nodes: [
      {
        id: 'EMP-7f3a',
        type: 'employee',
        label: 'EMP-7f3a',
        risk: 87,
        is_focus: true,
        tokenized: true,
      },
      { id: 'EMP-1a09', type: 'employee', label: 'EMP-1a09', risk: 78, tokenized: true },
      { id: 'BEN-9b1c', type: 'beneficiary', label: 'BEN-9b1c', risk: 71, tokenized: true },
      { id: 'BEN-2c7d', type: 'beneficiary', label: 'BEN-2c7d', risk: 55, tokenized: true },
      { id: 'ACCT-4d22', type: 'account', label: 'ACCT-4d22', tokenized: true },
      { id: 'WS-114', type: 'device', label: 'WS-114' },
      { id: 'IP-10.20.4.31', type: 'ip', label: '10.20.4.31' },
      { id: 'CUST-7711', type: 'customer', label: 'CUST-7711', tokenized: true },
    ],
    edges: [
      {
        id: 'e1',
        source: 'EMP-7f3a',
        target: 'EMP-1a09',
        type: 'maker_checker',
        label: 'maker→checker ×14',
        weight: 14,
        ring_id: 'RNG-12',
        collusion: true,
      },
      { id: 'e2', source: 'EMP-7f3a', target: 'BEN-9b1c', type: 'beneficiary', label: 'created' },
      {
        id: 'e3',
        source: 'EMP-7f3a',
        target: 'ACCT-4d22',
        type: 'transaction',
        label: '₹48,00,000',
        amount_inr: 4800000,
      },
      { id: 'e4', source: 'BEN-9b1c', target: 'ACCT-4d22', type: 'beneficiary' },
      { id: 'e5', source: 'EMP-7f3a', target: 'WS-114', type: 'shared_device' },
      {
        id: 'e6',
        source: 'EMP-1a09',
        target: 'WS-114',
        type: 'shared_device',
        label: 'shared device',
      },
      { id: 'e7', source: 'EMP-7f3a', target: 'IP-10.20.4.31', type: 'shared_ip' },
      { id: 'e8', source: 'EMP-7f3a', target: 'BEN-2c7d', type: 'beneficiary', label: 'created' },
      {
        id: 'e9',
        source: 'BEN-9b1c',
        target: 'CUST-7711',
        type: 'shared_address',
        label: 'shared address',
      },
    ],
    rings: [
      {
        ring_id: 'RNG-12',
        member_ids: ['EMP-7f3a', 'EMP-1a09'],
        motif: 'isolated maker-checker pair',
      },
    ],
    explainer: {
      model: 'GNNExplainer',
      node_ids: ['EMP-7f3a', 'EMP-1a09', 'BEN-9b1c'],
      edge_ids: ['e1', 'e2', 'e6'],
    },
  },
}

/* ───────────────────────────── Peer comparison (EMP-7f3a) ──────────────────────────────────── */
export const PEERS: Record<string, PeerComparisonResponse> = {
  'EMP-7f3a': {
    entity_id: 'EMP-7f3a',
    peer_group: 'PG-ops-tf',
    peer_count: 34,
    dimensions: [
      {
        key: 'off_hours_activity_rate_30d',
        label: 'Off-hours activity rate (30d)',
        unit: '%',
        actor_value: 41,
        z_score: 2.9,
        flagged: true,
        direction: 'higher_is_riskier',
        description: 'Share of actions outside 08:00–20:00 IST.',
        peer_distribution: {
          min: 0,
          p25: 3,
          median: 7,
          p75: 12,
          max: 22,
          mean: 8.2,
          stddev: 4.4,
          samples: [2, 4, 5, 6, 7, 7, 8, 9, 11, 12, 14, 18, 22, 41],
        },
      },
      {
        key: 'new_beneficiary_to_payment_latency_min',
        label: 'New-payee → payment latency (min)',
        unit: 'min',
        actor_value: 27,
        z_score: -2.4,
        flagged: true,
        direction: 'lower_is_riskier',
        description: 'Lower latency = less verification time before paying a brand-new payee.',
        peer_distribution: {
          min: 25,
          p25: 220,
          median: 480,
          p75: 1440,
          max: 4320,
          mean: 690,
          stddev: 410,
          samples: [27, 180, 220, 360, 480, 540, 720, 900, 1440, 2880, 4320],
        },
      },
      {
        key: 'amount_zscore_vs_peer',
        label: 'Payment amount z-score',
        unit: 'σ',
        actor_value: 3.4,
        z_score: 3.4,
        flagged: true,
        direction: 'higher_is_riskier',
        description: 'Standard deviations above the peer-group median single payment.',
        peer_distribution: {
          min: -1.5,
          p25: -0.4,
          median: 0.1,
          p75: 0.7,
          max: 1.9,
          mean: 0.15,
          stddev: 0.8,
          samples: [-1.2, -0.5, -0.2, 0, 0.1, 0.3, 0.5, 0.7, 1.1, 1.9, 3.4],
        },
      },
      {
        key: 'maker_checker_pair_frequency_30d',
        label: 'Same maker-checker pair freq (30d)',
        unit: 'count',
        actor_value: 14,
        z_score: 3.1,
        flagged: true,
        direction: 'higher_is_riskier',
        description: 'How often the same two people form the maker-checker pair.',
        peer_distribution: {
          min: 0,
          p25: 1,
          median: 2,
          p75: 4,
          max: 7,
          mean: 2.6,
          stddev: 1.7,
          samples: [0, 1, 1, 2, 2, 3, 4, 5, 6, 7, 14],
        },
      },
    ],
  },
}

/* ───────────────────────────── Unmask vault (synthetic) [Part 25.3] ────────────────────────── */
const VAULT: Record<string, string> = {
  'EMP-7f3a': 'Arjun Mehta — Officer, Trade Finance, Mumbai Main (synthetic)',
  'EMP-1a09': 'Neha Kulkarni — Officer (Checker), Trade Finance (synthetic)',
  'EMP-3c55': 'Vikram Rao — Database Administrator, IT Ops (synthetic)',
  'EMP-9d20': 'Priya Nair — Teller, Retail (resigning) (synthetic)',
  'BEN-9b1c': 'Sunrise Traders Pvt Ltd — A/C ●●●●4022, HDFC0001234 (synthetic)',
  'ACCT-4d22': 'A/C ●●●●●●4022 — Current (synthetic)',
}
export function unmaskValue(entityId: string): UnmaskResponse {
  return {
    entity_id: entityId,
    token: entityId,
    value: VAULT[entityId] ?? `${entityId} — re-identified (synthetic vault)`,
    audited: true,
    audit_id: `aud_${Math.abs(hash(entityId)).toString(16).slice(0, 6)}`,
  }
}

/* ───────────────────────────── Rules (change-controlled) ───────────────────────────────────── */
export const RULES: Rule[] = [
  {
    id: 'rule_new_ben_highvalue',
    name: 'New beneficiary then high value',
    code: 'NEW_BENEFICIARY_THEN_HIGHVALUE',
    description: 'Flag a high-value payment to a beneficiary created within the window.',
    type: 'threshold',
    enabled: true,
    status: 'active',
    version: 7,
    params: [
      { key: 'window_min', label: 'Beneficiary-age window', value: 60, unit: 'min' },
      { key: 'amount_inr', label: 'High-value threshold', value: 1000000, unit: 'INR' },
    ],
    updated_by: 'dgm.demo',
    updated_ts: '2026-06-15T06:30:00Z',
    history: [
      {
        version: 7,
        status: 'active',
        proposed_by: 'dgm.demo',
        approved_by: 'agm.demo',
        ts: '2026-06-15T06:30:00Z',
        summary: 'Lowered amount threshold 15L→10L',
        diff: [{ field: 'amount_inr', from: 1500000, to: 1000000 }],
      },
      {
        version: 6,
        status: 'active',
        proposed_by: 'dgm.demo',
        approved_by: 'agm.demo',
        ts: '2026-04-02T06:30:00Z',
        summary: 'Widened window 45→60 min',
        diff: [{ field: 'window_min', from: 45, to: 60 }],
      },
    ],
  },
  {
    id: 'rule_off_hours',
    name: 'Off-hours privileged activity',
    code: 'OFF_HOURS_ACTIVITY',
    description: 'Flag privileged actions outside business hours vs actor & peer baseline.',
    type: 'threshold',
    enabled: true,
    status: 'active',
    version: 4,
    params: [
      { key: 'start_hour', label: 'Business start (IST)', value: 8 },
      { key: 'end_hour', label: 'Business end (IST)', value: 20 },
    ],
    updated_by: 'dgm.demo',
    updated_ts: '2026-05-20T06:30:00Z',
  },
  {
    id: 'rule_maker_checker_pair',
    name: 'Isolated maker-checker pair',
    code: 'MAKER_CHECKER_SAME_PAIR',
    description: 'SoD: the same maker-checker pair recurs in isolation (collusion risk).',
    type: 'sod',
    enabled: true,
    status: 'active',
    version: 3,
    params: [{ key: 'pair_freq_30d', label: 'Pair frequency (30d)', value: 10, unit: 'count' }],
    updated_by: 'dgm.demo',
    updated_ts: '2026-06-01T06:30:00Z',
  },
  {
    id: 'rule_high_value_payment',
    name: 'High-value single payment',
    code: 'HIGH_VALUE_PAYMENT',
    description: 'Flag single payments above the absolute threshold.',
    type: 'threshold',
    enabled: true,
    status: 'pending_approval',
    version: 9,
    params: [{ key: 'amount_inr', label: 'Absolute threshold', value: 5000000, unit: 'INR' }],
    updated_by: 'dgm.demo',
    updated_ts: '2026-06-29T11:00:00Z',
    history: [
      {
        version: 9,
        status: 'pending_approval',
        proposed_by: 'dgm.demo',
        approved_by: null,
        ts: '2026-06-29T11:00:00Z',
        summary: 'Proposed lower threshold 50L→40L — awaiting four-eyes approval',
        diff: [{ field: 'amount_inr', from: 5000000, to: 4000000 }],
      },
    ],
  },
  {
    id: 'rule_privilege_self_grant',
    name: 'Privilege self-grant',
    code: 'PRIVILEGE_SELF_GRANT',
    description: 'SoD: actor grants themselves a privileged role without a change ticket.',
    type: 'sod',
    enabled: true,
    status: 'active',
    version: 2,
    params: [{ key: 'require_ticket', label: 'Require change ticket', value: true }],
    updated_by: 'dgm.demo',
    updated_ts: '2026-03-12T06:30:00Z',
  },
  {
    id: 'rule_dormant_reactivation',
    name: 'Dormant reactivation then debit',
    code: 'DORMANT_REACTIVATION_THEN_DEBIT',
    description: 'Flag a dormant account reactivated and debited within the window.',
    type: 'typology',
    enabled: false,
    status: 'draft',
    version: 1,
    params: [
      { key: 'dormant_days', label: 'Dormant period', value: 365, unit: 'days' },
      {
        key: 'debit_window_days',
        label: 'Debit window after reactivation',
        value: 7,
        unit: 'days',
      },
    ],
    updated_by: 'dgm.demo',
    updated_ts: '2026-06-27T06:30:00Z',
  },
]

/* ───────────────────────────── Models / drift / metrics (de-identified) ────────────────────── */
export const MODELS: ModelEntry[] = [
  {
    id: 'l2-ecod',
    name: 'L2 ECOD anomaly',
    layer: 'L2_unsupervised',
    version: '1.4.2',
    stage: 'champion',
    signed: true,
    promoted_by: 'datasci.demo',
    created_ts: '2026-05-10T00:00:00Z',
    metrics: { auc: 0.82, fpr: 0.07 },
    de_identified: true,
  },
  {
    id: 'l3-lgbm',
    name: 'L3 LightGBM',
    layer: 'L3_gbdt',
    version: '3.1.0',
    stage: 'champion',
    signed: true,
    promoted_by: 'datasci.demo',
    created_ts: '2026-06-01T00:00:00Z',
    metrics: {
      auc: 0.94,
      pr_auc: 0.71,
      precision: 0.66,
      recall: 0.78,
      f1: 0.71,
      fpr: 0.04,
      brier: 0.08,
    },
    de_identified: true,
  },
  {
    id: 'l3-catboost',
    name: 'L3 CatBoost (challenger)',
    layer: 'L3_gbdt',
    version: '0.9.3',
    stage: 'challenger',
    signed: true,
    promoted_by: null,
    created_ts: '2026-06-20T00:00:00Z',
    metrics: {
      auc: 0.95,
      pr_auc: 0.73,
      precision: 0.69,
      recall: 0.77,
      f1: 0.73,
      fpr: 0.04,
      brier: 0.07,
    },
    de_identified: true,
  },
  {
    id: 'l4-laxcat',
    name: 'L4 LAXCAT sequence',
    layer: 'L4_sequence',
    version: '0.6.1',
    stage: 'staging',
    signed: false,
    promoted_by: null,
    created_ts: '2026-06-25T00:00:00Z',
    metrics: { auc: 0.88, pr_auc: 0.62 },
    de_identified: true,
  },
  {
    id: 'l5-graphsage',
    name: 'L5 GraphSAGE',
    layer: 'L5_graph',
    version: '2.0.4',
    stage: 'champion',
    signed: true,
    promoted_by: 'datasci.demo',
    created_ts: '2026-05-28T00:00:00Z',
    metrics: { auc: 0.9, pr_auc: 0.68 },
    de_identified: true,
  },
  {
    id: 'l6-fusion',
    name: 'L6 fusion (calibrated)',
    layer: 'L6_fusion',
    version: '4.2.0',
    stage: 'champion',
    signed: true,
    promoted_by: 'datasci.demo',
    created_ts: '2026-06-10T00:00:00Z',
    metrics: {
      auc: 0.96,
      pr_auc: 0.79,
      precision: 0.72,
      recall: 0.81,
      f1: 0.76,
      fpr: 0.03,
      brier: 0.06,
    },
    de_identified: true,
  },
]

function driftPoints(base: number, slope: number, threshold: number) {
  return Array.from({ length: 8 }, (_, i) => ({
    ts: `2026-06-${String(23 + i).padStart(2, '0')}T00:00:00Z`,
    value: Number((base + slope * i).toFixed(3)),
    threshold,
  }))
}
export const DRIFT: DriftResponse = {
  generated_ts: '2026-06-30T03:00:00Z',
  series: [
    {
      model_id: 'l3-lgbm',
      feature: 'amount_zscore_vs_peer',
      metric: 'psi',
      status: 'warning',
      points: driftPoints(0.08, 0.012, 0.2),
    },
    {
      model_id: 'l3-lgbm',
      feature: 'new_beneficiary_to_payment_latency_min',
      metric: 'psi',
      status: 'drifting',
      points: driftPoints(0.12, 0.02, 0.2),
    },
    {
      model_id: 'l5-graphsage',
      feature: 'embedding_shift',
      metric: 'js',
      status: 'ok',
      points: driftPoints(0.04, 0.003, 0.15),
    },
    {
      model_id: 'l6-fusion',
      feature: 'score_distribution',
      metric: 'ks',
      status: 'ok',
      points: driftPoints(0.05, 0.004, 0.18),
    },
  ],
}

export const MODEL_QUALITY: ModelQualityResponse = {
  models: MODELS.filter((m) => m.metrics).map((m) => ({
    model_id: m.id,
    metrics: m.metrics!,
    trend: Array.from({ length: 6 }, (_, i) => ({
      ts: `2026-0${i + 1}-01T00:00:00Z`,
      metric: 'auc',
      value: Number(((m.metrics!.auc ?? 0.9) - 0.03 + i * 0.006).toFixed(3)),
    })),
  })),
}

/* ───────────────────────────── Audit (who-viewed-whom) ─────────────────────────────────────── */
export const AUDIT: AuditEvent[] = [
  {
    audit_id: 'aud_99f0c1',
    ts: '2026-06-30T03:10:00Z',
    actor: 'rm.demo',
    actor_role: 'relationship_manager',
    action: 'disposition',
    alert_id: 'alr_c4d2',
    entity_id: 'EMP-5e11',
    outcome: 'confirmed_fraud',
    detail: 'Confirmed unauthorised position',
    src_ip: '10.20.4.50',
  },
  {
    audit_id: 'aud_99f0b2',
    ts: '2026-06-30T03:05:00Z',
    actor: 'branch.demo',
    actor_role: 'branch_manager',
    action: 'unmask_pii',
    entity_id: 'EMP-7f3a',
    alert_id: 'alr_3d7e22',
    outcome: 'success',
    detail: 'Re-identified for case alr_3d7e22',
    src_ip: '10.20.4.51',
  },
  {
    audit_id: 'aud_99f0a3',
    ts: '2026-06-30T03:01:00Z',
    actor: 'rm.demo',
    actor_role: 'relationship_manager',
    action: 'view_entity',
    entity_id: 'EMP-7f3a',
    detail: 'Opened entity-360',
    src_ip: '10.20.4.50',
  },
  {
    audit_id: 'aud_99f094',
    ts: '2026-06-30T02:58:00Z',
    actor: 'rm.demo',
    actor_role: 'relationship_manager',
    action: 'assign',
    alert_id: 'alr_9a55',
    entity_id: 'EMP-7f3a',
    outcome: 'claimed',
    src_ip: '10.20.4.50',
  },
  {
    audit_id: 'aud_99f085',
    ts: '2026-06-30T02:50:00Z',
    actor: 'agm.demo',
    actor_role: 'agm_vigilance',
    action: 'view_audit',
    detail: 'Reviewed who-viewed-whom for EMP-3c55',
    src_ip: '10.20.4.60',
  },
  {
    audit_id: 'aud_99f076',
    ts: '2026-06-29T18:20:00Z',
    actor: 'dgm.demo',
    actor_role: 'dgm_compliance',
    action: 'rule_change_proposed',
    target: 'HIGH_VALUE_PAYMENT',
    detail: 'Proposed 50L→40L threshold',
    src_ip: '10.20.4.70',
  },
  {
    audit_id: 'aud_99f067',
    ts: '2026-06-29T12:00:00Z',
    actor: 'datasci.demo',
    actor_role: 'data_science_lead',
    action: 'promote_model',
    target: 'l3-catboost',
    outcome: 'pending_signoff',
    detail: 'Requested challenger promotion',
    src_ip: '10.20.4.80',
  },
  {
    audit_id: 'aud_99f058',
    ts: '2026-06-29T09:15:00Z',
    actor: 'cia.demo',
    actor_role: 'chief_internal_auditor',
    action: 'view_audit',
    detail: 'Exported audit slice 2026-06-22..29',
    src_ip: '10.20.4.90',
  },
  {
    audit_id: 'aud_99f049',
    ts: '2026-06-29T08:40:00Z',
    actor: 'itadmin.demo',
    actor_role: 'it_admin',
    action: 'create_user',
    target: 'newrm',
    detail: 'Provisioned relationship_manager role',
    src_ip: '10.20.4.10',
  },
  {
    audit_id: 'aud_99f03a',
    ts: '2026-06-28T22:05:00Z',
    actor: 'branch.demo',
    actor_role: 'branch_manager',
    action: 'view_entity',
    entity_id: 'EMP-3c55',
    detail: 'Opened entity-360 (privileged DBA)',
    src_ip: '10.20.4.51',
  },
  {
    audit_id: 'aud_99f02b',
    ts: '2026-06-28T19:30:00Z',
    actor: 'rm.demo',
    actor_role: 'relationship_manager',
    action: 'block_request',
    alert_id: 'alr_8c23',
    entity_id: 'EMP-5e11',
    outcome: 'pending_lead_approval',
    detail: 'Requested block — routed to Lead',
    src_ip: '10.20.4.50',
  },
  {
    audit_id: 'aud_99f01c',
    ts: '2026-06-28T10:00:00Z',
    actor: 'service.ingest',
    actor_role: 'service_account',
    action: 'audit_write',
    detail: 'Pipeline audit write',
    src_ip: '10.20.0.5',
  },
]

/* ───────────────────────────── Admin users (one per bank org-chart role) ───────────────────── */
export const USERS: AdminUser[] = [
  {
    id: 'u_rm',
    username: 'rm.demo',
    display_name: 'Asha Iyer',
    email: 'rm@bank.local',
    roles: ['relationship_manager'],
    status: 'active',
    created_ts: '2026-01-10T00:00:00Z',
    last_login: '2026-06-30T02:55:00Z',
  },
  {
    id: 'u_branch',
    username: 'branch.demo',
    display_name: 'Rohan Das',
    email: 'branch@bank.local',
    roles: ['branch_manager'],
    status: 'active',
    created_ts: '2025-11-01T00:00:00Z',
    last_login: '2026-06-30T03:04:00Z',
  },
  {
    id: 'u_cluster',
    username: 'cluster.demo',
    display_name: 'Vikas Shah',
    email: 'cluster@bank.local',
    roles: ['cluster_head'],
    status: 'active',
    created_ts: '2025-10-20T00:00:00Z',
    last_login: '2026-06-30T01:40:00Z',
  },
  {
    id: 'u_agm',
    username: 'agm.demo',
    display_name: 'Kavita Menon',
    email: 'agm@bank.local',
    roles: ['agm_vigilance'],
    status: 'active',
    created_ts: '2025-09-15T00:00:00Z',
    last_login: '2026-06-30T02:49:00Z',
  },
  {
    id: 'u_dgm',
    username: 'dgm.demo',
    display_name: 'Suresh Pillai',
    email: 'dgm@bank.local',
    roles: ['dgm_compliance'],
    status: 'active',
    created_ts: '2025-10-05T00:00:00Z',
    last_login: '2026-06-29T18:25:00Z',
  },
  {
    id: 'u_datasci',
    username: 'datasci.demo',
    display_name: 'Anil Kumar',
    email: 'datasci@bank.local',
    roles: ['data_science_lead'],
    status: 'active',
    created_ts: '2026-02-01T00:00:00Z',
    last_login: '2026-06-29T12:05:00Z',
  },
  {
    id: 'u_cgm',
    username: 'cgm.demo',
    display_name: 'Lakshmi Rao',
    email: 'cgm@bank.local',
    roles: ['cgm_risk'],
    status: 'active',
    created_ts: '2025-07-12T00:00:00Z',
    last_login: '2026-06-29T17:10:00Z',
  },
  {
    id: 'u_cia',
    username: 'cia.demo',
    display_name: 'Meera Joshi',
    email: 'cia@bank.local',
    roles: ['chief_internal_auditor'],
    status: 'active',
    created_ts: '2025-12-01T00:00:00Z',
    last_login: '2026-06-29T09:20:00Z',
  },
  {
    id: 'u_ed',
    username: 'ed.demo',
    display_name: 'Ravi Khanna',
    email: 'ed@bank.local',
    roles: ['executive_director'],
    status: 'active',
    created_ts: '2025-06-01T00:00:00Z',
    last_login: '2026-06-28T16:00:00Z',
  },
  {
    id: 'u_md',
    username: 'md.demo',
    display_name: 'Sunil Verma',
    email: 'md@bank.local',
    roles: ['managing_director'],
    status: 'active',
    created_ts: '2025-05-01T00:00:00Z',
    last_login: '2026-06-28T15:30:00Z',
  },
  {
    id: 'u_itadmin',
    username: 'itadmin.demo',
    display_name: 'Platform Admin',
    email: 'itadmin@bank.local',
    roles: ['it_admin'],
    status: 'active',
    created_ts: '2025-08-01T00:00:00Z',
    last_login: '2026-06-30T01:00:00Z',
  },
  {
    id: 'u_svc',
    username: 'service.ingest',
    display_name: 'Ingest Service Account',
    roles: ['service_account'],
    status: 'active',
    created_ts: '2025-08-01T00:00:00Z',
    last_login: null,
  },
]

/* ───────────────────────────── EWS / RFA coverage ──────────────────────────────────────────── */
export const EWS_COVERAGE: EwsCoverageResponse = {
  generated_ts: '2026-06-30T03:00:00Z',
  covered: 11,
  total: 14,
  indicators: [
    {
      code: 'EWS-01',
      label: 'Sudden spike in transaction volume',
      category: 'EWS',
      covered: true,
      source_layer: 'L2_unsupervised',
    },
    {
      code: 'EWS-02',
      label: 'Off-hours privileged activity',
      category: 'EWS',
      covered: true,
      source_layer: 'L1_rules',
      rule_id: 'rule_off_hours',
    },
    {
      code: 'EWS-03',
      label: 'New-beneficiary rapid payout',
      category: 'EWS',
      covered: true,
      source_layer: 'L1_rules',
      rule_id: 'rule_new_ben_highvalue',
    },
    {
      code: 'EWS-04',
      label: 'Dormant account reactivation',
      category: 'EWS',
      covered: false,
      note: 'Rule in draft (DORMANT_REACTIVATION_THEN_DEBIT)',
    },
    {
      code: 'EWS-05',
      label: 'Bulk data export by leaver',
      category: 'EWS',
      covered: true,
      source_layer: 'L4_sequence',
    },
    {
      code: 'EWS-06',
      label: 'Repeated maker-checker pairing',
      category: 'EWS',
      covered: true,
      source_layer: 'L5_graph',
      rule_id: 'rule_maker_checker_pair',
    },
    {
      code: 'EWS-07',
      label: 'Privilege self-grant',
      category: 'EWS',
      covered: true,
      source_layer: 'L1_rules',
      rule_id: 'rule_privilege_self_grant',
    },
    {
      code: 'RFA-01',
      label: 'Round-tripping / circular flows',
      category: 'RFA',
      covered: true,
      source_layer: 'L5_graph',
    },
    {
      code: 'RFA-02',
      label: 'Ghost employee / vendor',
      category: 'RFA',
      covered: true,
      source_layer: 'L5_graph',
    },
    {
      code: 'RFA-03',
      label: 'Self-appraised loan disbursal',
      category: 'RFA',
      covered: true,
      source_layer: 'L1_rules',
    },
    {
      code: 'RFA-04',
      label: 'Suspense / nostro lapping',
      category: 'RFA',
      covered: false,
      note: 'Slow-lane indicator — coverage planned',
    },
    {
      code: 'RFA-05',
      label: 'Trade-finance settlement mismatch',
      category: 'RFA',
      covered: true,
      source_layer: 'L1_rules',
    },
    {
      code: 'RFA-06',
      label: 'Treasury limit breach + delayed booking',
      category: 'RFA',
      covered: true,
      source_layer: 'L3_gbdt',
    },
    {
      code: 'RFA-07',
      label: 'Cross-channel identity reuse',
      category: 'RFA',
      covered: false,
      note: 'Pending shared-identity graph expansion',
    },
  ],
}

/* ───────────────────────────── Regulatory exports ──────────────────────────────────────────── */
export function reportFor(type: 'fmr' | 'crilc'): ReportExport {
  const confirmed = ALERTS.filter(
    (a) =>
      a.status === 'confirmed_fraud' || a.severity === 'critical' || a.exposure_inr >= 10000000,
  )
  const lineItems = confirmed.map((a) => ({
    ref: a.alert_id,
    entity_id: a.entity_id,
    alert_id: a.alert_id,
    amount_inr: a.exposure_inr,
    category: a.alert_type,
    detail: a.title,
  }))
  const header =
    type === 'fmr'
      ? 'ref,entity,amount_inr,category,detail'
      : 'ref,entity,amount_inr,classification,reported'
  const rows = lineItems.map(
    (l) =>
      `${l.ref},${l.entity_id},${l.amount_inr},${l.category},${(l.detail ?? '').replace(/,/g, ';')}`,
  )
  return {
    report_id: type === 'fmr' ? 'rpt_fmr_2026q2' : 'rpt_crilc_2026q2',
    type,
    status: 'ready',
    generated_ts: '2026-06-30T03:00:00Z',
    period: { from: '2026-04-01T00:00:00Z', to: '2026-06-30T00:00:00Z' },
    summary:
      type === 'fmr'
        ? 'FMR (Fraud Monitoring Return) draft — confirmed and high-exposure cases for the quarter, ready for MLRO review before RBI submission.'
        : 'CRILC export — exposures ≥ ₹3 crore aged ≥ 7 days within the 180-day window, formatted for the RBI CRILC return.',
    line_items: lineItems,
    download_filename: `${type}_2026q2.csv`,
    download_content: [header, ...rows].join('\n'),
  }
}

/* ───────────────────────────── KRIs (management + board / SCBMF) ───────────────────────────── */
export const KRIS: KriResponse = {
  generated_ts: '2026-06-30T03:00:00Z',
  cards: [
    {
      key: 'alert_volume_vs_capacity',
      label: 'Alert volume vs capacity',
      value: 86,
      unit: '%',
      target: 100,
      direction: 'lower_is_better',
      status: 'ok',
      delta: 4,
    },
    {
      key: 'mttd_hours',
      label: 'Mean time to detect',
      value: 6.2,
      unit: 'h',
      target: 12,
      direction: 'lower_is_better',
      status: 'ok',
      delta: -1.1,
    },
    {
      key: 'fpr',
      label: 'False-positive rate',
      value: 31,
      unit: '%',
      target: 35,
      direction: 'lower_is_better',
      status: 'ok',
      delta: -3,
    },
    {
      key: 'sla_compliance',
      label: 'SLA/TAT compliance (≤30d)',
      value: 93,
      unit: '%',
      target: 95,
      direction: 'higher_is_better',
      status: 'warning',
      delta: -1,
    },
    {
      key: 'open_high_severity',
      label: 'Open high/critical alerts',
      value: 7,
      unit: '',
      target: 5,
      direction: 'lower_is_better',
      status: 'warning',
      delta: 2,
    },
    {
      key: 'coverage',
      label: 'Typology coverage',
      value: 86,
      unit: '%',
      target: 90,
      direction: 'higher_is_better',
      status: 'warning',
      delta: 1,
    },
  ],
  trends: Array.from({ length: 12 }, (_, i) => ({
    period: `2026-W${String(15 + i).padStart(2, '0')}`,
    alerts: 40 + Math.round(18 * Math.sin(i / 2)) + i,
    confirmed: 6 + (i % 4),
    false_positives: 14 + Math.round(6 * Math.cos(i / 2)),
    mttd: Number((8 - i * 0.15).toFixed(1)),
  })),
  coverage: [
    { area: 'Trade finance', covered_pct: 92 },
    { area: 'Retail banking', covered_pct: 88 },
    { area: 'Treasury', covered_pct: 81 },
    { area: 'Credit / loans', covered_pct: 78 },
    { area: 'Payroll / HR', covered_pct: 74 },
    { area: 'IT / data layer', covered_pct: 85 },
  ],
}

/* ─────────────── Sub-threshold / ambient activity ('hidden 95%') [GET /activity/sub-threshold] ── */
export const SUB_THRESHOLD: SubThresholdResponse = {
  total_scored: 954,
  alerted: 4,
  sub_threshold: 950,
  emit_threshold: 70,
  bands: [
    { label: 'watch', min: 55, max: 70, count: 6 },
    { label: 'elevated', min: 40, max: 55, count: 4 },
    { label: 'low', min: 0, max: 40, count: 940 },
  ],
  watchlist: [
    { entity_id: 'EMP-2b14', score: 66, top_signal: 'off_hours_activity_rate_30d', ts: '2026-06-30T01:12:00Z' },
    { entity_id: 'EMP-9f77', score: 63, top_signal: 'maker_checker_pair_frequency_30d', ts: '2026-06-30T20:41:00Z' },
    { entity_id: 'EMP-3c55', score: 61, top_signal: 'db_rows_read_zscore_vs_peer', ts: '2026-06-29T22:05:00Z' },
    { entity_id: 'EMP-7a21', score: 58, top_signal: 'export_volume_vs_baseline', ts: '2026-06-30T02:47:00Z' },
    { entity_id: 'EMP-5d10', score: 57, top_signal: 'new_beneficiary_to_payment_latency_min', ts: '2026-06-30T19:58:00Z' },
    { entity_id: 'EMP-8b93', score: 55, top_signal: 'privileged_session_off_hours', ts: '2026-06-29T23:31:00Z' },
    { entity_id: 'EMP-1a09', score: 52, top_signal: 'amount_zscore_vs_peer', ts: '2026-06-30T13:20:00Z' },
    { entity_id: 'EMP-4d99', score: 48, top_signal: 'failed_login_burst', ts: '2026-06-30T09:05:00Z' },
    { entity_id: 'EMP-6e02', score: 44, top_signal: 'role_change_recency', ts: '2026-06-28T16:44:00Z' },
  ],
}

/* ───────────────────────────── Health ──────────────────────────────────────────────────────── */
export const HEALTH: HealthResponse = {
  status: 'degraded',
  version: '0.5.0',
  checked_ts: '2026-06-30T03:12:00Z',
  services: [
    { name: 'Backend API (FastAPI :8000)', status: 'ok', latency_ms: 22 },
    { name: 'ClickHouse :9000', status: 'ok', latency_ms: 14 },
    { name: 'Redis :6379', status: 'ok', latency_ms: 3 },
    { name: 'Postgres :5432', status: 'ok', latency_ms: 9 },
    { name: 'Kafka :9092', status: 'ok', latency_ms: 18 },
    {
      name: 'Model serving (ONNX/Triton :8001)',
      status: 'degraded',
      latency_ms: 240,
      detail: 'p99 latency above 200ms target',
    },
    { name: 'Keycloak :8080', status: 'ok', latency_ms: 31 },
    {
      name: 'Narrative gateway (NEAR AI / Groq)',
      status: 'ok',
      latency_ms: 410,
      detail: 'TEE attestation verified',
    },
  ],
}

export const METRICS_TEXT = `# HELP hawkeye_alerts_total Total alerts emitted
# TYPE hawkeye_alerts_total counter
hawkeye_alerts_total{severity="critical"} 12
hawkeye_alerts_total{severity="high"} 58
hawkeye_alerts_total{severity="medium"} 121
hawkeye_alerts_total{severity="low"} 240
# HELP hawkeye_fusion_latency_seconds L6 fusion latency
# TYPE hawkeye_fusion_latency_seconds histogram
hawkeye_fusion_latency_seconds_bucket{le="0.1"} 980
hawkeye_fusion_latency_seconds_bucket{le="0.5"} 1240
hawkeye_fusion_latency_seconds_bucket{le="+Inf"} 1260
`

/* ───────────────────────────── Cases (group alerts per entity) ─────────────────────────────── */
function caseFromEntity(entityId: string, status: CaseSummary['status']): CaseDetail {
  const entityAlerts = ALERTS.filter((a) => a.entity_id === entityId)
  const top = entityAlerts.reduce((m, a) => (a.risk_score > m.risk_score ? a : m), entityAlerts[0])
  const caseId = `case_${entityId.replace('EMP-', '').toLowerCase()}`
  return {
    case_id: caseId,
    title: top.title ?? `Investigation — ${entityId}`,
    entity_id: entityId,
    status,
    severity: top.severity,
    assignee: top.assignee ?? null,
    alert_ids: entityAlerts.map((a) => a.alert_id),
    created_ts: '2026-06-28T09:00:00Z',
    updated_ts: '2026-06-30T03:00:00Z',
    sla_due_ts: top.sla_due_ts,
    exposure_inr: entityAlerts.reduce((s, a) => s + a.exposure_inr, 0),
    alerts: entityAlerts,
    notes: [
      {
        id: 'n1',
        author: 'rm.demo',
        author_role: 'relationship_manager',
        ts: '2026-06-30T02:55:00Z',
        body: 'Opened case from triage queue. Linked 3 alerts for this entity.',
      },
      {
        id: 'n2',
        author: 'branch.demo',
        author_role: 'branch_manager',
        ts: '2026-06-30T03:02:00Z',
        body: 'Unmasked payee for verification (audited). Awaiting beneficiary confirmation.',
      },
    ],
    history: [
      {
        id: 'h1',
        ts: '2026-06-28T09:00:00Z',
        actor: 'system',
        action: 'case_created',
        detail: 'Auto-grouped alerts by entity',
      },
      {
        id: 'h2',
        ts: '2026-06-30T02:55:00Z',
        actor: 'rm.demo',
        actor_role: 'relationship_manager',
        action: 'assigned',
        detail: 'Claimed by rm.demo',
      },
      {
        id: 'h3',
        ts: '2026-06-30T03:00:00Z',
        actor: 'rm.demo',
        actor_role: 'relationship_manager',
        action: 'status_changed',
        detail: 'open → in_progress',
      },
    ],
  }
}

export const CASES: CaseDetail[] = [
  caseFromEntity('EMP-7f3a', 'in_progress'),
  caseFromEntity('EMP-1a09', 'open'),
  caseFromEntity('EMP-3c55', 'escalated'),
  caseFromEntity('EMP-9d20', 'open'),
  caseFromEntity('EMP-5e11', 'closed'),
]

export function findCase(id: string): CaseDetail | undefined {
  return CASES.find((c) => c.case_id === id)
}

/* ───────────────────────────── tiny stable hash (for synthetic audit ids) ──────────────────── */
function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  return h
}
