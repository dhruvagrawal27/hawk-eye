# Hawk-Eye — Bank Org-Chart Roles (RBAC) — FROZEN SPEC

> Single source of truth for the console role model. The backend (`rbac.py`, `schemas/common.py`,
> `sod.py`, `store/seed.py`), the frontend (`auth/capabilities.ts`, `lib/types.ts`, `auth/oidc.ts`,
> `app/nav-config.tsx`), and all tests/fixtures must match this exactly. Replaces the generic
> 8-role console model with a PSB (Union Bank-style) org chart, mapped onto RBI's **Three Lines of
> Defense**. Capability semantics and the 9 capabilities are unchanged — only the role identities,
> hierarchy, and two new oversight tiers are new.

## Two role axes (do not conflate)
- **Console/RBAC roles (THIS doc):** who uses the fraud console + what they may do. Replaced here.
- **Actor/subject roles** in `data/sim/*` (ops_maker, ops_checker, trade_finance, …): the *monitored*
  employees inside events; they drive detection and are **unchanged**.

## The 9 capabilities (unchanged)
`view_alerts · triage_assign · disposition · request_block · unmask_pii · tune_rules ·
train_deploy_models · view_audit · admin`

Grant semantics: `A`=allow ✅ · `C("note")`=conditional ⚠️ (route enforces the note) · `X`=deny ❌.

## Roles (12: 11 human + 1 service) — enum value → metadata

| key (enum value) | label | short | tier | line | dept | reports_to | default_route |
|---|---|---|---|---|---|---|---|
| `relationship_manager` | Relationship Manager | RM | Branch | 1st | Branch Ops | `branch_manager` | `/triage` |
| `branch_manager` | Branch Manager | Branch Mgr | Branch | 1st | Branch Ops | `cluster_head` | `/triage` |
| `cluster_head` | Cluster Head (Zonal Manager) | Cluster | Cluster/Zone | 1st | Zonal Office | `agm_vigilance` | `/triage` |
| `agm_vigilance` | AGM — Vigilance & Fraud Risk | AGM Vig | Dept (HO) | 1st | Fraud Risk Mgmt (FRMD) | `cgm_risk` | `/triage` |
| `dgm_compliance` | DGM — Risk & Compliance | DGM Comp | Dept (HO) | 2nd | Risk & Compliance | `cgm_risk` | `/compliance` |
| `data_science_lead` | Head — Data Science / Model Risk | Data Sci | Dept (HO) | 2nd | Analytics / Model Risk | `cgm_risk` | `/models` |
| `cgm_risk` | CGM — Chief Risk Officer | CGM Risk | Executive | 2nd | Risk & Compliance | `executive_director` | `/reports` |
| `chief_internal_auditor` | Chief Internal Auditor | CIA | Dept (HO) | 3rd | Internal Audit | `managing_director` | `/audit` |
| `executive_director` | Executive Director | ED | Board | Exec | Board | `managing_director` | `/reports` |
| `managing_director` | Managing Director & CEO | MD&CEO | Board | Exec | Board | `null` | `/reports` |
| `it_admin` | IT / Platform Administrator | IT Admin | Dept (IT) | — | Technology | `null` | `/admin` |
| `service_account` | Service Account | Service | System | — | System | `null` | `/` |

`HUMAN_ROLES` (demo persona picker, excludes `service_account`), top-of-chart first:
`managing_director, executive_director, cgm_risk, dgm_compliance, agm_vigilance, chief_internal_auditor,
data_science_lead, cluster_head, branch_manager, relationship_manager, it_admin`

## Capability matrix (verbatim — columns in order: view, triage, disposition, request_block, unmask, tune, train, audit, admin)

```
relationship_manager:   C("assigned_only"), A, A, C("request_only"), C("case_scoped_logged"), X, X, X, X
branch_manager:         A, A, A, A, C("logged"), X, X, C("view_own"), X
cluster_head:           A, A, C("override"), C("approve"), C("logged"), C("propose_only"), X, A, X
agm_vigilance:          A, A, C("override"), C("approve"), C("logged"), C("change_controlled"), X, A, X
dgm_compliance:         A, X, X, X, C("logged"), C("change_controlled"), X, A, X
data_science_lead:      C("de_identified_only"), X, X, X, X, X, C("with_signoff"), C("view_own"), X
cgm_risk:               C("de_identified_only"), X, X, X, X, C("change_controlled"), X, A, X
chief_internal_auditor: C("read_only"), X, X, X, X, X, X, A, X
executive_director:     C("de_identified_only"), X, X, X, X, X, X, A, X
managing_director:      C("de_identified_only"), X, X, X, X, X, X, A, X
it_admin:               X, X, X, X, X, X, C("deploy_infra_only"), A, A
service_account:        C("scoped_token"), X, X, X, X, X, X, C("write_only"), X
```

`assert_matrix_complete()` → **12 roles × 9 capabilities**.

`canViewCaseData` = true only when `view_alerts` is allowed AND scope is not `de-identified`/`none`
AND role ≠ service_account. So exec/board (CGM, ED, MD) and Data Science see **de-identified
aggregates only** (no case PII); RM/Branch/Cluster/AGM/DGM/CIA see case data.

## Separation of Duties (sod.py) — carried over, re-keyed
- A model deployer cannot label/close alerts: `data_science_lead` is denied `disposition`/`triage_assign`
  contextually (it's already `X` statically, but keep the SoD reason for clarity).
- An investigator cannot tune the rule that generated their own alert: applies to
  `relationship_manager`, `branch_manager`, `cluster_head` for `tune_rules` when `isOwnRule`.
- New: a maker/checker in the monitored population is an actor-role concern (data), not a console role.

## old → new mapping (mechanical rename across tests/fixtures/seed; capability profile preserved)
```
analyst              -> relationship_manager
senior_investigator  -> branch_manager
team_lead            -> agm_vigilance        # the fraud-function lead / MLRO
compliance_officer   -> dgm_compliance
auditor              -> chief_internal_auditor
model_engineer       -> data_science_lead
platform_admin       -> it_admin
service_account      -> service_account      # unchanged
```
NEW (additive, no old equivalent): `cluster_head, cgm_risk, executive_director, managing_director`.

## Demo personas (mock login / seed users) — username → role
```
EMP-rm01  relationship_manager      EMP-cgm1  cgm_risk
EMP-bm01  branch_manager            EMP-cia1  chief_internal_auditor
EMP-ch01  cluster_head              EMP-ds01  data_science_lead
EMP-agm1  agm_vigilance             EMP-ed01  executive_director
EMP-dgm1  dgm_compliance            EMP-md01  managing_director
EMP-it01  it_admin                  svc-ingest service_account
```
Keep the legacy demo logins working as aliases where tests rely on them (e.g. `EMP-tl01` → `agm_vigilance`,
`EMP-an01` → `relationship_manager`) so the A→Z flow and existing tests stay green.

## Org-chart view (new)
A `/org` screen (visible to managers+exec) renders the reporting tree above, grouped by the three
Lines of Defense, each node a role card (label, short-code, capability summary, headcount). Read-only.
