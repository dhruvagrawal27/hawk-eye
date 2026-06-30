# =============================================================================
# Hawk-Eye — Data-residency OPA/Rego policy (Conftest).
# Blueprint: Part 16 (RBI data-localization — all data & compute on-prem in
#            India) · Part 9.3 (data residency: everything in-India) ·
#            Part 26.1 (AWS pilot pinned to ap-south-1 / Mumbai for residency).
# PLATFORM task: PLATFORM-9 (residency OPA/Conftest policy).
# -----------------------------------------------------------------------------
# FAILS the build (conftest test) if ANY rendered Kubernetes workload:
#   (a) is missing the label  data-residency: in-india  on its pod template, OR
#   (b) is missing the label  region                    on its pod template, OR
#   (c) pins a `region` that is NOT an approved India region.
#
# Run against rendered manifests:
#   helm template hawk-eye deploy/k8s/charts/hawk-eye | conftest test -
#
# Tested for conftest 0.56.0 / OPA 0.70.0 (BOM: security_tools.conftest).
# =============================================================================
package main

import rego.v1

# --- Canonical residency constants (mirror values.yaml global.residency) -----

# The mandatory data-residency label value (RBI on-prem India localization).
required_data_residency := "in-india"

# Approved India regions. ap-south-1 = Mumbai (the pilot, Part 26.1);
# ap-south-2 = Hyderabad. Any other region value is a residency violation.
india_regions := {"ap-south-1", "ap-south-2"}

# Workload kinds whose POD TEMPLATE must carry residency labels. These are the
# kinds that actually schedule pods (and thus place data/compute somewhere).
pod_carrying_kinds := {
	"Deployment",
	"StatefulSet",
	"DaemonSet",
	"ReplicaSet",
	"Job",
	"Pod",
}

# --- Helpers -----------------------------------------------------------------

# True if the document under test is a pod-carrying workload kind.
is_pod_workload if {
	input.kind in pod_carrying_kinds
}

# Resolve the labels that must carry residency: for a bare Pod that's
# metadata.labels; for controllers it's spec.template.metadata.labels.
pod_labels := labels if {
	input.kind == "Pod"
	labels := object.get(input, ["metadata", "labels"], {})
}

pod_labels := labels if {
	input.kind != "Pod"
	labels := object.get(input, ["spec", "template", "metadata", "labels"], {})
}

# Human-readable name for messages.
workload_name := name if {
	name := object.get(input, ["metadata", "name"], "<unnamed>")
}

# --- DENY rules (each violation fails `conftest test`) ------------------------

# (a) Missing the data-residency label entirely.
deny contains msg if {
	is_pod_workload
	not pod_labels["data-residency"]
	msg := sprintf(
		"RESIDENCY VIOLATION [Part 16/9.3]: %s/%s pod template is missing required label 'data-residency: %s'",
		[input.kind, workload_name, required_data_residency],
	)
}

# (b) data-residency present but not the required in-india value.
deny contains msg if {
	is_pod_workload
	val := pod_labels["data-residency"]
	val != required_data_residency
	msg := sprintf(
		"RESIDENCY VIOLATION [Part 16/9.3]: %s/%s has data-residency=%q, must be %q",
		[input.kind, workload_name, val, required_data_residency],
	)
}

# (c) Missing the region label entirely.
deny contains msg if {
	is_pod_workload
	not pod_labels.region
	msg := sprintf(
		"RESIDENCY VIOLATION [Part 26.1]: %s/%s pod template is missing required 'region' label (must be an India region)",
		[input.kind, workload_name],
	)
}

# (d) region present but pinned to a non-India region.
deny contains msg if {
	is_pod_workload
	region := pod_labels.region
	not india_regions[region]
	msg := sprintf(
		"RESIDENCY VIOLATION [Part 26.1]: %s/%s pins non-India region %q; allowed: %v",
		[input.kind, workload_name, region, india_regions],
	)
}

# --- WARN rule (advisory, does not fail the build) ---------------------------

# Encourage the ALERT-ONLY golden-rule annotation on workloads (informational).
warn contains msg if {
	is_pod_workload
	not object.get(input, ["metadata", "annotations", "hawk-eye/golden-rule-alert-only"], false)
	msg := sprintf(
		"ADVISORY [golden-rule]: %s/%s lacks annotation 'hawk-eye/golden-rule-alert-only: \"true\"'",
		[input.kind, workload_name],
	)
}
