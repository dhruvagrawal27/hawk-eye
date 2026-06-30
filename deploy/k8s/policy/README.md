# Hawk-Eye — Residency policy (OPA / Conftest)

> Blueprint: **Part 16** (RBI data-localization — all data & compute on-prem in
> India) · **Part 9.3** (data residency: everything in-India) · **Part 26.1**
> (AWS pilot pinned to `ap-south-1` / Mumbai). PLATFORM task **PLATFORM-9**.

This directory holds the **policy-as-code residency gate**. It FAILS CI (and any
local check) if **any rendered Kubernetes workload** is missing the
`data-residency: in-india` label, is missing a `region` label, or pins a
**non-India** region. This is the machine-checkable enforcement of the on-prem
India-localization golden rule.

## Files

| File | Purpose |
|---|---|
| `residency.rego` | The policy. `deny` rules (build-failing) for the four residency violation classes + an advisory `warn` for the alert-only annotation. `package main` so plain `conftest test` picks it up. |
| `residency_test.rego` | Unit tests (`conftest verify`) proving the policy passes a compliant workload and fails each violation class — *guards the guard*. |
| `fixtures/good-workload.yaml` | Compliant example → PASSES. |
| `fixtures/bad-workload.yaml` | Deliberately non-compliant → FAILS (demo only; never apply). |

## What it checks (the `deny` rules)

For every **pod-carrying** kind (`Deployment`, `StatefulSet`, `DaemonSet`,
`ReplicaSet`, `Job`, `Pod`) it inspects the **pod template labels**
(`spec.template.metadata.labels`, or `metadata.labels` for a bare `Pod`):

1. **Missing** `data-residency` label → FAIL.
2. `data-residency` present but **not** `in-india` → FAIL.
3. **Missing** `region` label → FAIL.
4. `region` present but **not** an approved India region
   (`ap-south-1` Mumbai, `ap-south-2` Hyderabad) → FAIL.

Non-pod kinds (e.g. `Service`, `NetworkPolicy`, `PodDisruptionBudget`) are not
residency-gated and pass through.

## Run it

The canonical one-liner — render the chart and pipe rendered manifests to
`conftest test -` (reads policy from `./policy` by default; pass `-p` explicitly
when running from elsewhere):

```bash
# From repo root:
helm template hawk-eye deploy/k8s/charts/hawk-eye \
  | conftest test --policy deploy/k8s/policy -
```

Expected result on a correct chart: **all rendered Deployments pass** (Services /
PDBs / NetworkPolicies are not gated). Output ends with `... tests, 0 failures`.

Prove the gate actually bites (negative fixture must FAIL):

```bash
conftest test --policy deploy/k8s/policy deploy/k8s/policy/fixtures/bad-workload.yaml
# -> 2 failures: missing data-residency label + non-India region us-east-1
```

Run the policy's own unit tests:

```bash
conftest verify --policy deploy/k8s/policy
```

## Versions

`conftest 0.56.0` / OPA `0.70.0` (see `deploy/versions.bom.yaml :: security_tools.conftest`).
The policy uses `import rego.v1`, which is stable on these versions.

## CI

Wire this into CI as a gate (PLATFORM-9 / Part 16). Suggested step:

```bash
helm template hawk-eye deploy/k8s/charts/hawk-eye | conftest test --policy deploy/k8s/policy -
conftest verify --policy deploy/k8s/policy
```

A non-zero exit blocks the merge — residency is non-negotiable (RBI localization).
