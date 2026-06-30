# Zero-Trust Network Policy (PLATFORM-10)

> **Purpose.** Define the zero-trust network posture for Hawk-Eye: map every service tier to a
> micro-segmented **security zone**, fix the **NAT egress allow-list** (NEAR AI + Groq ONLY),
> mandate **default-deny** east-west traffic with **mTLS + per-hop authn**, and state how this is
> enforced in code (Kubernetes `NetworkPolicy`, the Terraform `network` module, and the
> SPIFFE/mTLS layer).
>
> **Blueprint:** Part 26.2 (AWS security — VPC private subnets, SG/NACL least-open, NAT egress
> allow-list, mTLS), Part 19.3 (segmentation / zero-trust / no-egress air-gap posture).
> **Task:** PLATFORM-10. **Status:** SCAFFOLD (real cloud = Terraform PLAN-ONLY; never apply).

---

## 0. Golden-rule alignment

- **ALERT-ONLY.** This policy governs *network reachability*; it never blocks a user transaction
  or auto-actions a fraud event. It constrains how Hawk-Eye's own services may talk to each other
  and to the outside world.
- **ON-PREM + SYNTHETIC + NO INTERNET EGRESS.** The running system has **no general internet
  egress**. The *only* outbound destinations permitted are the two LLM gateways (NEAR AI + Groq),
  via a NAT allow-list, and even those are reachable **only** from the governance/serving zone for
  the TEE-attested LLM call path (PLATFORM-14). Everything else is denied by default.
- **VALIDATE-AGAINST-BLUEPRINT.** Tiering and zoning follow the Part 9.1 reference topology; the
  air-gap + egress posture follows Part 19.3 and Part 26.2.

---

## 1. Zero-trust principles (the non-negotiables)

1. **Default deny, everywhere.** No pod, subnet, or security group permits traffic unless an
   explicit rule allows it. Both ingress and egress start at *deny-all*.
2. **Authenticate every hop.** No implicit trust from network location. Every service-to-service
   call is mutually authenticated with **mTLS** using a per-service **SPIFFE identity**
   (`spiffe://hawk-eye/ns/default/sa/<service>`; see `deploy/mtls/`), not a shared secret or a
   "we're on the same VLAN so it's fine" assumption.
3. **Least privilege / micro-segmentation.** A service may reach **only** the specific peers its
   function requires (e.g. `backend → serving`, `backend → postgres`), never the whole subnet.
   Each Kubernetes `ServiceAccount` (`deploy/mtls/service-accounts.yaml`) is unique and minimally
   scoped; **no shared or anonymous accounts** (Part 19.3 — the exact insider anti-pattern this
   platform exists to catch).
4. **No internet egress except the LLM allow-list.** Outbound to the internet is denied for the
   whole system; a single NAT path allows **only** `cloud-api.near.ai` and `api.groq.com`.
5. **Assume breach.** Lateral movement is contained by zone boundaries; the data zone is never
   directly reachable from the edge; the management zone is reachable only through PAM
   (`pam-shim`, PLATFORM-15).
6. **Audit the path.** Denied connections and policy changes are observable (flow logs / OTel /
   the WORM audit log) so "who tried to reach what" is investigable.

---

## 2. Security zones

Hawk-Eye is partitioned into **six** zones. A zone is both a *network* boundary (subnet / SG /
NetworkPolicy namespace-label) and a *trust* boundary. Traffic **between** zones is allowed only on
the explicit edges in §3; traffic **within** a zone is still default-deny and opened per peer.

| Zone | Cloud placement (Part 26.2) | K8s label (`hawk-eye.zone=`) | Members (CONTEXT.md §7) | Internet egress |
|---|---|---|---|---|
| **edge** | Public subnet — **ALB/WAF only** | `edge` | ALB + WAF (PLATFORM-7); no app pods | none (terminates inbound TLS) |
| **app** | Private subnet (app) | `app` | `backend` (8000), `frontend` (5173), `keycloak` (8080), `governance-api` (8093), `hitl-gate` (8094) | none |
| **data** | Private subnet (data) — **most isolated** | `data` | `postgres` (5432), `clickhouse` (8123/9000), `redis` (6379), `minio` (9001/9002), `kafka` (9092), `schema-registry` (8085), `flink-jobmanager` (8081) | none |
| **compute / serving** | Private subnet (compute) | `compute` | `serving` (8001), `mlflow` (5000), `airflow` (8088) | **NAT allow-list only** (LLM path) |
| **governance** | Private subnet (compute/control) | `governance` | `tee-attestation` (8090), `pam-shim` (8091), `degradation-switch` (8092), `vault` (8200) | **NAT allow-list only** (TEE→LLM) |
| **management** | Private subnet (mgmt) — **PAM-gated** | `management` | `prometheus` (9090), `grafana` (3000), `alertmanager` (9093), `otel-collector` (4317/4318/8889), ArgoCD (8083), admin/bastion | none (scrape-out only) |

> **Why six.** The blueprint asks for tier segmentation + micro-segmentation. We separate the
> *data plane* (data) from the *model plane* (compute/serving) from the *control plane*
> (governance) from *operations* (management), so that a compromise of, say, an observability
> exporter cannot reach the model registry or the synthetic data store, and the LLM-egress
> capability is confined to the two zones (compute, governance) that actually make the TEE-attested
> call.

---

## 3. Allowed inter-zone edges (everything else: DENY)

Read as **source → destination : reason**. All edges are mTLS + authn (no plaintext, no anonymous).

| # | Source zone | Dest zone | Port(s) | Purpose |
|---|---|---|---|---|
| E1 | Internet | **edge** | 443 | Inbound investigator/API traffic, TLS-terminated at ALB/WAF |
| E2 | **edge** | **app** | 8000, 8080, 5173 | ALB → backend / keycloak / frontend only |
| E3 | **app** | **data** | 5432, 8123, 9000, 6379, 9092, 8085, 9001 | backend/governance-api read app + governance + analytics + cache + bus |
| E4 | **app** | **compute** | 8001 | backend → serving (KServe v2 inference) |
| E5 | **app** | **governance** | 8090, 8091, 8092, 8093, 8094, 8200 | backend/hitl → TEE attest, PAM check, degradation switch, vault read |
| E6 | **compute** | **data** | 9092, 8085, 8123, 9001 | Flink/serving/Airflow consume bus, schemas, features, objects |
| E7 | **compute** | **governance** | 8090 | serving/airflow → TEE-attestation before any LLM call |
| E8 | **governance** | **NAT → internet** | 443 | TEE-attested LLM call to `cloud-api.near.ai` / `api.groq.com` **ONLY** |
| E9 | **compute** | **NAT → internet** | 443 | (optional) serving LLM-explain via the same allow-list **ONLY** |
| E10 | **management** | app/data/compute/governance | scrape ports (e.g. 8889, 9090 targets, `/metrics`) | Prometheus scrape, OTel collection — **read-only**, one-directional |
| E11 | **management** | **app/compute/governance** | service ports (via PAM) | platform-admin break-glass, **only** through `pam-shim` (PLATFORM-15) |

**Default-deny statement (normative):**

> *Any flow not enumerated in §3 is DENIED. There is no default-allow fallback, no "temporarily open
> 0.0.0.0/0", and no plaintext peer. Ingress and egress both begin at deny-all on every zone, every
> namespace, and every security group. New edges require a four-eyes change (PLATFORM-15 /
> change-mgmt) and a corresponding `NetworkPolicy` + Terraform SG rule — never an ad-hoc opening.*

Explicit denials worth naming:
- **edge → data**: DENIED. The internet-facing zone can never reach Postgres/ClickHouse/MinIO/Kafka.
- **data → internet / data → app**: DENIED. The data zone makes no outbound calls and never initiates
  to the app tier (it is called, it does not call).
- **anything → management** except scrape responses and PAM: DENIED.
- **any zone → internet** except E8/E9 to the two LLM hosts: DENIED.

---

## 4. NAT egress allow-list (the only internet path)

The system has **no general internet egress**. A single NAT path exists for the LLM gateway calls
required by the TEE-attested explanation flow (PLATFORM-14), and it is constrained to **exactly two
fully-qualified destinations on 443**:

| Allowed FQDN | Service | Used by zone(s) | Secret (by reference only) |
|---|---|---|---|
| `cloud-api.near.ai` | NEAR AI gateway | governance, compute | `NEAR_AI_API_KEY` |
| `api.groq.com` | Groq gateway | governance, compute | `GROQ_API_KEY` |

Rules:
- **No wildcards.** The allow-list is FQDN-pinned (egress firewall / proxy FQDN allow-list); not a
  CIDR, not `*.near.ai`. DNS for any other name resolves to a sink / is dropped.
- **No other egress.** Package installs, telemetry to vendors, OS updates, container pulls in the
  *running* system: all denied. Images are pulled at build time in CI, then run from a private
  registry inside the perimeter.
- **Secrets by reference.** `NEAR_AI_API_KEY` and `GROQ_API_KEY` are held in Vault (on-prem) /
  Secrets Manager + SSM (AWS) and injected at runtime — **never hardcoded** (Part 26.1; see
  `deploy/secrets/`).
- **On-prem = full air-gap option.** In the on-prem (`target=onprem`) deployment the LLM path can be
  pointed at an internal gateway or disabled entirely; Hawk-Eye degrades to **rules-only** scoring
  (the `degradation-switch`, PLATFORM-4) with no loss of the alert-only guarantee.

This allow-list is the single most security-sensitive control in PLATFORM-10 and must match
CONTEXT.md / `deploy/versions.bom.yaml` egress posture exactly.

---

## 5. mTLS + authn on every hop (zero-trust between components)

Network zoning is necessary but **not sufficient** — zero-trust does not trust the network even
inside a zone. Therefore:

- **Identity.** Every service has a unique SPIFFE ID `spiffe://hawk-eye/ns/default/sa/<service>`,
  issued by the dev CA (`deploy/mtls/gen-certs.sh`) and, in the real fabric, by **SPIRE**
  (`deploy/mtls/spire/`). See `deploy/mtls/README.md`.
- **Mutual TLS.** All east-west traffic is mTLS: both client and server present and verify certs.
  No service accepts plaintext or one-way TLS from a peer.
- **Authorization.** On top of mTLS identity, service-to-service authorization uses the SPIFFE ID
  (and, for user-facing flows, the Keycloak OIDC token + SoD role, PLATFORM-33). A valid network
  path is **not** sufficient to call an endpoint — the caller's identity must be on that endpoint's
  allow-list.
- **No shared accounts.** One `ServiceAccount` per service
  (`deploy/mtls/service-accounts.yaml`); zero shared/anonymous credentials (Part 19.3).
- **Short-lived creds.** SPIRE-issued SVIDs are short-TTL and auto-rotated; the IAM layer
  (`infra/terraform/modules/iam`, owned by the Terraform agent) uses roles, **no long-lived keys**.

---

## 6. How this is enforced in code (references)

| Control | Enforced by | Path |
|---|---|---|
| Default-deny + per-edge allow (K8s) | Kubernetes `NetworkPolicy` (CNI: Calico/Cilium) | `deploy/k8s/policy/` (NetworkPolicy manifests) |
| Zone subnets, ALB-only public subnet, least-open SG/NACL, NAT egress allow-list | Terraform **network** module | `infra/terraform/modules/network/` *(owned by the Terraform agent; PLAN-ONLY)* |
| Per-service identity + mTLS | dev CA + SPIFFE/SPIRE | `deploy/mtls/` (`gen-certs.sh`, `spire/`, `service-accounts.yaml`) |
| Least-privilege IAM roles, no long-lived keys | Terraform **iam** module | `infra/terraform/modules/iam/` *(owned by the Terraform agent)* |
| Secrets by reference (LLM keys, PII key) | Vault / Secrets Manager + SSM | `deploy/secrets/` |
| Policy-as-code residency + zero-trust checks | OPA / Conftest in CI | `.github/workflows` + `deploy/k8s/policy/` |

> **Note on ownership.** The Terraform `network` and `iam` modules are authored by the Terraform
> workstream; this document is the *policy* they implement and the *contract* CI checks against. If
> a zone, edge, or the egress allow-list changes here, the module and the `NetworkPolicy` manifests
> must change in lockstep (and vice-versa) under a four-eyes change.

---

## 7. Verification checklist (CI / review)

- [ ] Every zone's `NetworkPolicy` starts `deny-all` (ingress + egress) before any allow.
- [ ] No SG/NACL rule opens `0.0.0.0/0` except the ALB ingress (443) in the edge zone.
- [ ] NAT egress allow-list contains **exactly** `cloud-api.near.ai` + `api.groq.com`, no wildcards.
- [ ] `edge → data` has **no** path; `data → internet` has **no** path.
- [ ] Every service has a unique SPIFFE ID + `ServiceAccount`; no `default`/shared account in use.
- [ ] All inter-service traffic is mTLS (no plaintext listener exposed across a zone boundary).
- [ ] Management reaches workloads only via scrape (read) + PAM (`pam-shim`) — never directly.
- [ ] No secret value is hardcoded; LLM/PII keys referenced from Vault/SSM only.
