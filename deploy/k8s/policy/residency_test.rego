# =============================================================================
# Hawk-Eye — Unit tests for the residency policy (`conftest verify`).
# Blueprint: Part 16 / Part 9.3 / Part 26.1. PLATFORM task: PLATFORM-9.
# -----------------------------------------------------------------------------
# Proves the policy both PASSES a compliant workload and FAILS each violation
# class (missing label, wrong value, missing region, non-India region). Run:
#   conftest verify --policy deploy/k8s/policy
# These tests guard the guard — a broken policy that silently passes everything
# would defeat the residency gate.
# =============================================================================
package main

import rego.v1

# A fully compliant Deployment (the happy path).
compliant_deployment := {
	"kind": "Deployment",
	"metadata": {
		"name": "hawk-eye-backend",
		"annotations": {"hawk-eye/golden-rule-alert-only": "true"},
	},
	"spec": {"template": {"metadata": {"labels": {
		"data-residency": "in-india",
		"region": "ap-south-1",
	}}}},
}

# Compliant workload => no deny messages.
test_compliant_deployment_passes if {
	count(deny) == 0 with input as compliant_deployment
}

# Missing data-residency label => denied.
test_missing_data_residency_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "remove",
		"path": "/spec/template/metadata/labels/data-residency",
	}])
	count(deny) > 0 with input as bad
}

# Wrong data-residency value => denied.
test_wrong_data_residency_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/metadata/labels/data-residency",
		"value": "us-east",
	}])
	count(deny) > 0 with input as bad
}

# Missing region label => denied.
test_missing_region_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "remove",
		"path": "/spec/template/metadata/labels/region",
	}])
	count(deny) > 0 with input as bad
}

# Non-India region => denied.
test_non_india_region_denied if {
	bad := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/metadata/labels/region",
		"value": "us-east-1",
	}])
	count(deny) > 0 with input as bad
}

# ap-south-2 (Hyderabad) is also accepted.
test_hyderabad_region_passes if {
	ok := json.patch(compliant_deployment, [{
		"op": "replace",
		"path": "/spec/template/metadata/labels/region",
		"value": "ap-south-2",
	}])
	count(deny) == 0 with input as ok
}

# Non-pod kinds (e.g. Service) are NOT residency-gated => no deny.
test_service_not_gated if {
	svc := {"kind": "Service", "metadata": {"name": "hawk-eye-backend"}}
	count(deny) == 0 with input as svc
}

# A bare Pod missing labels is also caught.
test_bare_pod_missing_labels_denied if {
	pod := {"kind": "Pod", "metadata": {"name": "rogue", "labels": {}}}
	count(deny) > 0 with input as pod
}
