-- =============================================================================
-- Hawk-Eye — Governance DB schema (PLATFORM-32, blueprint Part 27.2 inventory + Part 34)
-- Postgres-native DDL (the canonical schema). The governance-api + seed + go-live tooling
-- use SQLAlchemy models (governance/db/models.py) that mirror this exactly, so they also
-- run on SQLite for local/CI. Records are keyed to model_version / release where relevant
-- (Part 27.2 MRM inventory) and surfaced in the dashboard governance view via governance-api.
-- =============================================================================

-- Board-approved policies (AI policy, BCP, data-protection, etc.) — PLATFORM-36
CREATE TABLE IF NOT EXISTS policies (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    policy_type     TEXT NOT NULL,            -- ai_policy | bcp | dpia | data_protection | lawful_basis | breach | transparency
    version         TEXT NOT NULL DEFAULT '1.0',
    status          TEXT NOT NULL DEFAULT 'draft',   -- draft | board_approved | retired
    approved_by     TEXT,                     -- signatory/body
    approval_date   DATE,
    resolution_id   TEXT,                     -- board resolution id
    doc_path        TEXT,                     -- generated md/pdf (PLATFORM-36)
    summary         TEXT
);

-- Governance bodies (AI/Model-Risk Committee, Ethics Committee, ISC, ITSC, Board) — PLATFORM-35
CREATE TABLE IF NOT EXISTS committees (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    committee_type  TEXT NOT NULL,            -- ai_model_risk | ethics | isc | itsc | board | audit
    charter         TEXT,
    cadence         TEXT
);

CREATE TABLE IF NOT EXISTS committee_members (
    id              SERIAL PRIMARY KEY,
    committee_id    INTEGER REFERENCES committees(id),
    member_name     TEXT NOT NULL,
    member_role     TEXT,                     -- chair | member | secretary
    org_function    TEXT                      -- risk | compliance | business | tech | legal | hr | independent
);

CREATE TABLE IF NOT EXISTS committee_minutes (
    id              SERIAL PRIMARY KEY,
    committee_id    INTEGER REFERENCES committees(id),
    meeting_date    DATE NOT NULL,
    agenda          TEXT,
    decisions       TEXT,
    model_version   TEXT,                     -- when a model approval/review is on the agenda
    attendees       TEXT
);

-- Generic approvals / sign-offs (independent validation, CAB, model promotion) — PLATFORM-34/19
CREATE TABLE IF NOT EXISTS approvals (
    id              SERIAL PRIMARY KEY,
    artifact_type   TEXT NOT NULL,            -- model_validation | cab_change | model_promotion | dpia_signoff | bcp
    artifact_ref    TEXT,                     -- fk-ish ref to the artifact (name/id)
    model_version   TEXT,                     -- keyed to model version where relevant
    decision        TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    approver        TEXT,
    approver_role   TEXT,                     -- independent_validator | cab | model_risk_committee
    approval_date   DATE,
    resolution_id   TEXT,
    notes           TEXT
);

-- Model validation reports (SR 11-7 / Part 27.2) — PLATFORM-34
CREATE TABLE IF NOT EXISTS model_validations (
    id                  SERIAL PRIMARY KEY,
    model_name          TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    risk_tier           TEXT,                 -- tier-1..tier-4 by impact
    conceptual_soundness TEXT,
    data_quality        TEXT,
    performance         TEXT,
    stability           TEXT,
    outcomes            TEXT,
    llm_grounding       TEXT,                 -- grounding/hallucination for the LLM gateway
    validator           TEXT,                 -- independent of developers (effective challenge)
    signoff_status      TEXT DEFAULT 'pending',  -- pending | signed_off | rejected
    signoff_date        DATE,
    report_path         TEXT
);

-- Vendor / outsourcing register (AWS + NEAR AI/Groq) — PLATFORM-38
CREATE TABLE IF NOT EXISTS vendors (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,        -- AWS | NEAR AI | Groq
    vendor_type         TEXT,                 -- cloud | llm_gateway
    due_diligence       TEXT,
    sla                 TEXT,
    exit_strategy       TEXT,
    concentration_risk  TEXT,
    ai_clauses          TEXT,                 -- algorithmic bias / subcontractor AI / data confidentiality
    sbom_ref            TEXT,                 -- linkage to PLATFORM-17 SBOM
    status              TEXT DEFAULT 'assessed'
);

-- DPIA / data-protection records (DPO, audit, lawful basis) — PLATFORM-36
CREATE TABLE IF NOT EXISTS dpia (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    scope           TEXT,                     -- e.g. employee-monitoring
    lawful_basis    TEXT,                     -- DPDP closed legitimate-uses mapping
    risk_rating     TEXT,
    dpo             TEXT,                     -- India-resident DPO
    status          TEXT DEFAULT 'draft',     -- draft | approved
    approval_date   DATE,
    audit_report    TEXT                      -- annual independent data-protection audit
);

-- Incidents (AI incidents, cyber, breaches) + regulatory reporting — PLATFORM-35/36/30
CREATE TABLE IF NOT EXISTS incidents (
    id              SERIAL PRIMARY KEY,
    incident_type   TEXT NOT NULL,            -- ai_model | cyber | personal_data_breach
    severity        TEXT,
    description     TEXT,
    model_version   TEXT,
    reported_to     TEXT,                     -- DPB | CERT-In | RBI
    report_deadline TEXT,                     -- e.g. CERT-In 6h
    status          TEXT DEFAULT 'open',
    opened_ts       TIMESTAMP DEFAULT now(),
    closed_ts       TIMESTAMP
);

-- Security assurance reports (VAPT, ATLAS red-team, model-risk review) — PLATFORM-23
CREATE TABLE IF NOT EXISTS security_reports (
    id              SERIAL PRIMARY KEY,
    report_type     TEXT NOT NULL,            -- vapt | redteam | model_risk
    scope           TEXT,
    findings_count  INTEGER DEFAULT 0,
    critical_count  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',   -- pending | passed | failed
    signoff         TEXT,
    model_version   TEXT,
    report_date     DATE,
    report_path     TEXT
);

-- UAT sign-off (investigator UAT) — PLATFORM-24
CREATE TABLE IF NOT EXISTS uat_signoffs (
    id              SERIAL PRIMARY KEY,
    scenario        TEXT NOT NULL,
    cases_total     INTEGER DEFAULT 0,
    cases_passed    INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',   -- pending | signed_off
    signoff         TEXT,
    signoff_date    DATE,
    report_path     TEXT
);

-- Operating-model metrics: override-rate / alert-fatigue (trust calibration) — PLATFORM-39
CREATE TABLE IF NOT EXISTS operating_metrics (
    id              SERIAL PRIMARY KEY,
    metric          TEXT NOT NULL,            -- override_rate | alert_fatigue | mttd | precision_at_k
    value           DOUBLE PRECISION,
    period          TEXT,
    computed_ts     TIMESTAMP DEFAULT now()
);

-- Staffing plans (Erlang headcount/roster) — PLATFORM-39
CREATE TABLE IF NOT EXISTS staffing_plans (
    id              SERIAL PRIMARY KEY,
    scenario        TEXT NOT NULL,
    alert_volume    INTEGER,
    handling_min    DOUBLE PRECISION,
    sla_hours       DOUBLE PRECISION,
    headcount       INTEGER,
    roster          TEXT
);

-- Go-live readiness checklist (Part 34.6 ticks) — PLATFORM-41
CREATE TABLE IF NOT EXISTS go_live_ticks (
    id              SERIAL PRIMARY KEY,
    category        TEXT NOT NULL,            -- regulatory | security | reliability | quality | data | operating_model | program
    item            TEXT NOT NULL,
    evidence_table  TEXT,                     -- which table proves it
    evidence_filter TEXT,                     -- a simple key=value filter resolved by the checklist service
    status          TEXT DEFAULT 'not_met',   -- met | not_met | partial
    evidence_ref    TEXT,
    updated_ts      TIMESTAMP DEFAULT now()
);

-- governance-api's own action audit (quis custodiet — even governance reads are audited)
CREATE TABLE IF NOT EXISTS governance_audit (
    id              SERIAL PRIMARY KEY,
    actor           TEXT,
    action          TEXT,
    target          TEXT,
    ts              TIMESTAMP DEFAULT now()
);
