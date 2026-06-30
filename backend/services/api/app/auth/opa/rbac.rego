# Hawk-Eye RBAC + SoD policy bundle (BACKEND-3, blueprint Part 24.1 / 19.6).
#
# This is the deployable OPA bundle. The authoritative LOCAL evaluator is app/auth/rbac.py +
# app/auth/sod.py (Python), kept in lockstep with this policy; PLATFORM hosts OPA 8.x and the API
# can be configured to consult it instead of the in-process matrix without changing call sites.
#
# Decision: data.hawkeye.rbac.allow  (with input {role, capability, context})
package hawkeye.rbac

import future.keywords.if
import future.keywords.in

# allow|conditional|deny per (role, capability). ⚠️ conditional cells carry a constraint the
# caller must additionally enforce (case-scope, de-identify, logging, sign-off).
matrix := {
    "analyst": {
        "view_alerts": "conditional", "triage_assign": "allow", "disposition": "allow",
        "request_block": "conditional", "unmask_pii": "conditional", "tune_rules": "deny",
        "train_deploy_models": "deny", "view_audit": "deny", "admin": "deny",
    },
    "senior_investigator": {
        "view_alerts": "allow", "triage_assign": "allow", "disposition": "allow",
        "request_block": "allow", "unmask_pii": "conditional", "tune_rules": "deny",
        "train_deploy_models": "deny", "view_audit": "conditional", "admin": "deny",
    },
    "team_lead": {
        "view_alerts": "allow", "triage_assign": "allow", "disposition": "conditional",
        "request_block": "conditional", "unmask_pii": "conditional", "tune_rules": "conditional",
        "train_deploy_models": "deny", "view_audit": "allow", "admin": "deny",
    },
    "compliance_officer": {
        "view_alerts": "allow", "triage_assign": "deny", "disposition": "deny",
        "request_block": "deny", "unmask_pii": "conditional", "tune_rules": "conditional",
        "train_deploy_models": "deny", "view_audit": "allow", "admin": "deny",
    },
    "auditor": {
        "view_alerts": "conditional", "triage_assign": "deny", "disposition": "deny",
        "request_block": "deny", "unmask_pii": "deny", "tune_rules": "deny",
        "train_deploy_models": "deny", "view_audit": "allow", "admin": "deny",
    },
    "model_engineer": {
        "view_alerts": "conditional", "triage_assign": "deny", "disposition": "deny",
        "request_block": "deny", "unmask_pii": "deny", "tune_rules": "deny",
        "train_deploy_models": "conditional", "view_audit": "conditional", "admin": "deny",
    },
    "platform_admin": {
        "view_alerts": "deny", "triage_assign": "deny", "disposition": "deny",
        "request_block": "deny", "unmask_pii": "deny", "tune_rules": "deny",
        "train_deploy_models": "conditional", "view_audit": "allow", "admin": "allow",
    },
    "service_account": {
        "view_alerts": "conditional", "triage_assign": "deny", "disposition": "deny",
        "request_block": "deny", "unmask_pii": "deny", "tune_rules": "deny",
        "train_deploy_models": "deny", "view_audit": "conditional", "admin": "deny",
    },
}

grant := matrix[input.role][input.capability]

default allow := false

allow if grant == "allow"
allow if grant == "conditional"

# --- SoD overrides (Part 19.6): deny even where the matrix would allow ----------------------
default sod_denied := false

# A model deployer may not write labels (disposition) or close their own alerts.
sod_denied if {
    input.capability == "disposition"
    matrix[input.role]["train_deploy_models"] != "deny"
}

# An investigator may not tune the rules that generate their own alerts.
sod_denied if {
    input.capability == "tune_rules"
    input.role in {"analyst", "senior_investigator"}
    count(input.context.assigned_alerts_from_rule) > 0
}

# Final decision used by callers.
decision := "deny" if sod_denied
decision := grant if not sod_denied
