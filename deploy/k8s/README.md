# Hawk-Eye — Kubernetes / Helm (PLATFORM-9)

> Blueprint: **Part 9.1** (reference topology) · **Part 9.3** (data residency,
> HA/DR, least-privilege) · **Part 16** (RBI data-localization) · **Part 19.3**
> (micro-segmentation / zero-trust / no internet egress) · **Part 26** (AWS
> `ap-south-1` pilot) · **Part 30.1** (HA / graceful degradation). Task **PLATFORM-9**.

This is the **on-prem / Lightsail Kubernetes deployment** of the full Hawk-Eye
platform: one Helm chart that renders a `Deployment` + `Service` for **every**
core, application and platform workload, plus default-deny **micro-segmentation**
NetworkPolicies, `PodDisruptionBudget`s, rolling-update strategy and
readiness/liveness probes — and a **data-residency policy gate** (OPA/Conftest)
that fails the build if any workload could place data/compute outside India.

> **SCAFFOLD.** Rendering and policy checks run fully offline. Actually
> *deploying* needs a real Kubernetes **1.31** cluster (BOM pin) with a CNI that
> enforces `NetworkPolicy` (e.g. Calico/Cilium). Secret **values** are never in
> this chart — they are referenced and must be synced from Vault/SSM first.

## Layout

```
deploy/k8s/
├── README.md                     # this file
├── charts/hawk-eye/              # the umbrella Helm chart
│   ├── Chart.yaml                # apiVersion v2, kubeVersion ">=1.31 <1.32"
│   ├── values.yaml               # workloads map, BOM image tags, residency, HA
│   ├── .helmignore
│   └── templates/
│       ├── _helpers.tpl          # naming + MANDATORY residency-label helper
│       ├── deployment.yaml       # one Deployment per workload (loop)
│       ├── service.yaml          # one ClusterIP Service per workload (loop)
│       ├── networkpolicy.yaml    # default-deny + DNS + per-peer allows
│       ├── poddisruptionbudget.yaml
│       └── NOTES.txt
└── policy/                       # OPA/Conftest residency gate (see policy/README.md)
    ├── residency.rego
    ├── residency_test.rego
    └── fixtures/{good,bad}-workload.yaml
```

## Workloads rendered

Every entry in `values.yaml :: workloads` gets a Deployment + Service (+ PDB for
HA workloads, + NetworkPolicy allows). Tiers:

- **core** — `kafka`, `schema-registry`, `flink-jobmanager`, `flink-taskmanager`,
  `redis`, `clickhouse`, `postgres`, `minio`
- **app** — `serving`, `backend`, `keycloak`, `mlflow`, `airflow`
- **platform** — `prometheus`, `grafana`, `degradation-switch`,
  `tee-attestation`, `pam-shim`, `vault`, `governance-api`, `hitl-gate`

Image tags come from `deploy/versions.bom.yaml` (the BOM is the single source of
truth; CI's `bom-drift` gate enforces no drift). First-party stubs use the
`hawkeye/*` image refs.

## Residency guarantee (Part 9.3 / Part 16)

`templates/_helpers.tpl :: hawk-eye.residencyLabels` stamps **every** object and
**every pod template** with:

```yaml
data-residency: in-india
region: ap-south-1            # Mumbai — India data-residency (Part 26.1)
```

These come from `values.yaml :: global.residency` and are **not** overridable per
workload. The OPA policy in `policy/` then fails any render that lacks them.

## Zero-trust networking (Part 19.3)

`templates/networkpolicy.yaml` renders:
1. a namespace-wide **default-deny** (ingress + egress);
2. a narrow **DNS egress** allow to `kube-system` so Service discovery works;
3. per-workload **ingress allows** generated from each workload's `allowFrom`;
4. reciprocal **egress allows** for those declared peers.

Internet egress (the NEAR AI + Groq allow-list) is enforced at the **NAT / VPC**
layer by Terraform (Part 26.2), not here — k8s NetworkPolicy cannot match
external FQDNs. Nothing in this chart opens outbound internet egress.

## HA / continuity (Part 30.1)

- `RollingUpdate` with `maxUnavailable: 0` → zero-downtime upgrades.
- `readinessProbe` + `livenessProbe` on every workload (HTTP or TCP).
- `PodDisruptionBudget` (`minAvailable: 1`) for every workload with `replicas > 1`.
- `topologySpreadConstraints` spread replicas across nodes (multi-rack, Part 9.3).
- HA replica counts: `serving`, `backend`, `degradation-switch`, `flink-taskmanager` = 2.

---

## Commands

All commands run from the **repo root**. Tooling pins: `helm` (k8s 1.31 client),
`conftest 0.56.0` / OPA `0.70.0` (BOM).

### 1. Lint the chart

```bash
helm lint deploy/k8s/charts/hawk-eye
```

### 2. Render the manifests (no cluster needed)

```bash
helm template hawk-eye deploy/k8s/charts/hawk-eye
```

Render a single template while iterating:

```bash
helm template hawk-eye deploy/k8s/charts/hawk-eye -s templates/deployment.yaml
```

### 3. Run the residency check (the gate)

```bash
helm template hawk-eye deploy/k8s/charts/hawk-eye \
  | conftest test --policy deploy/k8s/policy -
```

Expected: every rendered Deployment **passes** (`0 failures`). Prove the gate
bites with the negative fixture:

```bash
conftest test --policy deploy/k8s/policy deploy/k8s/policy/fixtures/bad-workload.yaml   # -> FAIL
```

Run the policy's unit tests:

```bash
conftest verify --policy deploy/k8s/policy
```

### 4. Deploy (SCAFFOLD — needs a real 1.31 cluster + CNI + synced secrets)

```bash
# 1) create the namespace + sync secrets from Vault/SSM (out of scope here)
# 2) install:
helm install hawk-eye deploy/k8s/charts/hawk-eye -n hawk-eye --create-namespace
# 3) verify residency labels landed on every pod:
kubectl -n hawk-eye get pods \
  -L data-residency,region -l app.kubernetes.io/part-of=hawk-eye
```

## CI wiring (suggested)

```bash
helm lint deploy/k8s/charts/hawk-eye
helm template hawk-eye deploy/k8s/charts/hawk-eye | conftest test --policy deploy/k8s/policy -
conftest verify --policy deploy/k8s/policy
```

A non-zero exit from any step blocks the merge: residency (RBI localization) and
zero-trust segmentation are non-negotiable golden-rule controls.
