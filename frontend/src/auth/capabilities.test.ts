import { describe, expect, it } from 'vitest'
import {
  CAPABILITIES,
  can,
  canViewCaseData,
  constraintFor,
  MATRIX,
  violatesSoD,
  type Capability,
  type Role,
} from './capabilities'

/**
 * RBAC matrix tests — assert the encoded MATRIX against an INDEPENDENT truth table transcribed from
 * the FROZEN bank org-chart spec (docs/BANK_ROLES.md capability matrix). Parametrized over all 12
 * roles × 9 capabilities, plus the ⚠️ constraints and the SoD rule (Part 19.6). If anyone edits a
 * cell, this catches it.
 */

// allowed? per role × capability — transcribed straight from the BANK_ROLES.md matrix.
const EXPECTED: Record<Role, Record<Capability, boolean>> = {
  relationship_manager: {
    view_alerts: true,
    triage: true,
    disposition: true,
    request_block: true,
    unmask_pii: true,
    tune_rules: false,
    train_models: false,
    view_audit: false,
    admin: false,
  },
  branch_manager: {
    view_alerts: true,
    triage: true,
    disposition: true,
    request_block: true,
    unmask_pii: true,
    tune_rules: false,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  cluster_head: {
    view_alerts: true,
    triage: true,
    disposition: true,
    request_block: true,
    unmask_pii: true,
    tune_rules: true,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  agm_vigilance: {
    view_alerts: true,
    triage: true,
    disposition: true,
    request_block: true,
    unmask_pii: true,
    tune_rules: true,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  dgm_compliance: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: true,
    tune_rules: true,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  data_science_lead: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: true,
    view_audit: true,
    admin: false,
  },
  cgm_risk: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: true,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  chief_internal_auditor: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  executive_director: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  managing_director: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: false,
    view_audit: true,
    admin: false,
  },
  it_admin: {
    view_alerts: false,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: true,
    view_audit: true,
    admin: true,
  },
  service_account: {
    view_alerts: true,
    triage: false,
    disposition: false,
    request_block: false,
    unmask_pii: false,
    tune_rules: false,
    train_models: false,
    view_audit: true,
    admin: false,
  },
}

const ROLES = Object.keys(EXPECTED) as Role[]

describe('RBAC capability matrix (BANK_ROLES.md)', () => {
  it('is exactly 12 roles × 9 capabilities', () => {
    expect(ROLES).toHaveLength(12)
    for (const role of ROLES) {
      expect(Object.keys(MATRIX[role])).toHaveLength(9)
    }
  })

  for (const role of ROLES) {
    for (const cap of CAPABILITIES) {
      it(`${role} · ${cap} = ${EXPECTED[role][cap] ? '✅/⚠️' : '❌'}`, () => {
        expect(can(role, cap)).toBe(EXPECTED[role][cap])
        expect(MATRIX[role][cap].allowed).toBe(EXPECTED[role][cap])
      })
    }
  }

  it('encodes the ⚠️ constraints exactly', () => {
    expect(constraintFor('relationship_manager', 'unmask_pii')).toBe('case_scoped_logged')
    expect(constraintFor('relationship_manager', 'request_block')).toBe('request_only')
    expect(constraintFor('branch_manager', 'unmask_pii')).toBe('logged')
    expect(constraintFor('cluster_head', 'disposition')).toBe('override')
    expect(constraintFor('cluster_head', 'request_block')).toBe('approve')
    expect(constraintFor('cluster_head', 'tune_rules')).toBe('propose_only')
    expect(constraintFor('agm_vigilance', 'disposition')).toBe('override')
    expect(constraintFor('agm_vigilance', 'tune_rules')).toBe('change_controlled')
    expect(constraintFor('dgm_compliance', 'tune_rules')).toBe('change_controlled')
    expect(constraintFor('cgm_risk', 'tune_rules')).toBe('change_controlled')
    expect(constraintFor('data_science_lead', 'view_alerts')).toBe('de_identified_only')
    expect(constraintFor('data_science_lead', 'train_models')).toBe('with_signoff')
    expect(constraintFor('chief_internal_auditor', 'view_alerts')).toBe('read_only')
    expect(constraintFor('it_admin', 'train_models')).toBe('deploy_infra_only')
    expect(constraintFor('service_account', 'view_alerts')).toBe('scoped_token')
  })

  it('encodes view scope (assigned / all / read-only / de-identified / none)', () => {
    expect(MATRIX.relationship_manager.view_alerts.scope).toBe('assigned')
    expect(MATRIX.branch_manager.view_alerts.scope).toBe('all')
    expect(MATRIX.cluster_head.view_alerts.scope).toBe('all')
    expect(MATRIX.chief_internal_auditor.view_alerts.scope).toBe('read-only')
    expect(MATRIX.data_science_lead.view_alerts.scope).toBe('de-identified')
    expect(MATRIX.it_admin.view_alerts.scope).toBe('none')
  })
})

describe('canViewCaseData', () => {
  it('excludes de-identified-only, no-case-data and service roles', () => {
    expect(canViewCaseData('relationship_manager')).toBe(true)
    expect(canViewCaseData('branch_manager')).toBe(true)
    expect(canViewCaseData('cluster_head')).toBe(true)
    expect(canViewCaseData('agm_vigilance')).toBe(true)
    expect(canViewCaseData('dgm_compliance')).toBe(true)
    expect(canViewCaseData('chief_internal_auditor')).toBe(true) // read-only, but still case data
    expect(canViewCaseData('data_science_lead')).toBe(false) // de-identified only
    expect(canViewCaseData('cgm_risk')).toBe(false) // de-identified only
    expect(canViewCaseData('executive_director')).toBe(false) // de-identified only
    expect(canViewCaseData('managing_director')).toBe(false) // de-identified only
    expect(canViewCaseData('it_admin')).toBe(false) // no case data
    expect(canViewCaseData('service_account')).toBe(false)
    expect(canViewCaseData(undefined)).toBe(false)
  })
})

describe('SoD rule (Part 19.6)', () => {
  it('a model deployer cannot label/close (disposition) or triage', () => {
    expect(violatesSoD('data_science_lead', 'disposition')).toMatch(/separation of duties/i)
    expect(violatesSoD('data_science_lead', 'triage')).toMatch(/separation of duties/i)
  })
  it('an investigator cannot tune the rule that generated their own alert', () => {
    expect(violatesSoD('relationship_manager', 'tune_rules', { isOwnRule: true })).toMatch(
      /separation of duties/i,
    )
    expect(violatesSoD('branch_manager', 'tune_rules', { isOwnRule: true })).toMatch(
      /separation of duties/i,
    )
    expect(violatesSoD('cluster_head', 'tune_rules', { isOwnRule: true })).toMatch(
      /separation of duties/i,
    )
  })
  it('returns null when SoD does not apply', () => {
    expect(violatesSoD('relationship_manager', 'disposition')).toBeNull()
    expect(violatesSoD('dgm_compliance', 'tune_rules', { isOwnRule: false })).toBeNull()
  })
})
