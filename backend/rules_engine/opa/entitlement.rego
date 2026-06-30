# Hawk-Eye least-privilege / entitlement OPA policy (BACKEND-6, blueprint Part 3.4 / 8).
#
# Evaluates whether an actor's exercised duties violate Separation-of-Duties / least-privilege.
# The Python engine (rules_engine/sod_matrix.py) is the authoritative local evaluator; this is the
# deployable OPA 8.x bundle (PLATFORM hosts the runtime), kept in lockstep.
#
# input  = { actor_id, held_entitlements: [..], exercised: [..], maker_checker, partner }
# output = data.hawkeye.entitlement.{toxic_combinations, self_grant, maker_checker_same, deny}
package hawkeye.entitlement

import future.keywords.if
import future.keywords.in

# Toxic duty pairs that must be separated (mirror DEFAULT_CONFLICTS).
conflicts := [
    {"create_beneficiary", "approve_payment"},
    {"create_vendor", "approve_payment"},
    {"initiate_loan", "approve_loan"},
    {"create_user", "grant_entitlement"},
    {"maker", "checker"},
    {"trade_capture", "trade_settlement"},
]

held := {e | some e in input.held_entitlements}

# A toxic combination exists if the actor holds BOTH sides of any conflict pair.
toxic_combinations[pair] if {
    some pair in conflicts
    pair_subset(pair, held)
}

pair_subset(pair, s) if {
    every e in pair {
        e in s
    }
}

# Self-grant: actor granted/approved their own entitlement.
default self_grant := false
self_grant if input.self_grant == true

# Maker == checker on the same item.
default maker_checker_same := false
maker_checker_same if input.maker_checker_same_actor == true

# Aggregate deny decision for the gateway.
default deny := false
deny if count(toxic_combinations) > 0
deny if self_grant
deny if maker_checker_same
