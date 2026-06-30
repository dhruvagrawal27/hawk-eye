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
 * blueprint Part 24.1 (l.879–886). Parametrized over all 8 roles × 9 capabilities, plus the ⚠️
 * constraints and the SoD rule (Part 19.6). If anyone edits a cell, this catches it.
 */

// allowed? per role × capability — transcribed straight from the blueprint table.
const EXPECTED: Record<Role, Record<Capability, boolean>> = {
  analyst: {
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
  senior_investigator: {
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
  team_lead: {
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
  compliance_officer: {
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
  auditor: {
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
  model_engineer: {
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
  platform_admin: {
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

describe('RBAC capability matrix (Part 24.1)', () => {
  for (const role of ROLES) {
    for (const cap of CAPABILITIES) {
      it(`${role} · ${cap} = ${EXPECTED[role][cap] ? '✅/⚠️' : '❌'}`, () => {
        expect(can(role, cap)).toBe(EXPECTED[role][cap])
        expect(MATRIX[role][cap].allowed).toBe(EXPECTED[role][cap])
      })
    }
  }

  it('encodes the ⚠️ constraints exactly', () => {
    expect(constraintFor('analyst', 'unmask_pii')).toBe('case-scoped, logged')
    expect(constraintFor('senior_investigator', 'unmask_pii')).toBe('logged')
    expect(constraintFor('team_lead', 'unmask_pii')).toBe('logged')
    expect(constraintFor('team_lead', 'disposition')).toBe('override')
    expect(constraintFor('team_lead', 'request_block')).toBe('approve')
    expect(constraintFor('team_lead', 'tune_rules')).toBe('propose')
    expect(constraintFor('compliance_officer', 'tune_rules')).toBe('change-controlled')
    expect(constraintFor('model_engineer', 'view_alerts')).toBe('de-identified only')
    expect(constraintFor('model_engineer', 'train_models')).toBe('with sign-off')
    expect(constraintFor('platform_admin', 'train_models')).toBe('deploy infra')
  })

  it('encodes view scope (assigned / all / read-only / de-identified / none)', () => {
    expect(MATRIX.analyst.view_alerts.scope).toBe('assigned')
    expect(MATRIX.senior_investigator.view_alerts.scope).toBe('all')
    expect(MATRIX.auditor.view_alerts.scope).toBe('read-only')
    expect(MATRIX.model_engineer.view_alerts.scope).toBe('de-identified')
    expect(MATRIX.platform_admin.view_alerts.scope).toBe('none')
  })
})

describe('canViewCaseData', () => {
  it('excludes de-identified-only, no-case-data and service roles', () => {
    expect(canViewCaseData('analyst')).toBe(true)
    expect(canViewCaseData('senior_investigator')).toBe(true)
    expect(canViewCaseData('team_lead')).toBe(true)
    expect(canViewCaseData('compliance_officer')).toBe(true)
    expect(canViewCaseData('auditor')).toBe(true) // read-only, but still case data
    expect(canViewCaseData('model_engineer')).toBe(false) // de-identified only
    expect(canViewCaseData('platform_admin')).toBe(false) // no case data
    expect(canViewCaseData('service_account')).toBe(false)
    expect(canViewCaseData(undefined)).toBe(false)
  })
})

describe('SoD rule (Part 19.6)', () => {
  it('a model deployer cannot label/close (disposition) or triage', () => {
    expect(violatesSoD('model_engineer', 'disposition')).toMatch(/separation of duties/i)
    expect(violatesSoD('model_engineer', 'triage')).toMatch(/separation of duties/i)
  })
  it('an investigator cannot tune the rule that generated their own alert', () => {
    expect(violatesSoD('analyst', 'tune_rules', { isOwnRule: true })).toMatch(
      /separation of duties/i,
    )
    expect(violatesSoD('senior_investigator', 'tune_rules', { isOwnRule: true })).toMatch(
      /separation of duties/i,
    )
  })
  it('returns null when SoD does not apply', () => {
    expect(violatesSoD('analyst', 'disposition')).toBeNull()
    expect(violatesSoD('compliance_officer', 'tune_rules', { isOwnRule: false })).toBeNull()
  })
})
