# mTLS + SPIFFE/SPIRE workload identity (PLATFORM-11)

> **Purpose.** Give every Hawk-Eye service a unique, cryptographic **workload identity**
> (a SPIFFE ID) and require **mutual TLS** on every internal hop — so that no service trusts
> another by network location, and there are **no shared or anonymous accounts**.
>
> **Blueprint:** Part 26.2 (IAM / mTLS), Part 9.3, Part 19.3 (no shared/anonymous accounts — the
> exact insider anti-pattern Hawk-Eye exists to catch). **Task:** PLATFORM-11.
> **Status:** SCAFFOLD — the dev CA path is REAL locally; the SPIRE path goes live on the real
> fabric. Pinned images: `ghcr.io/spiffe/spire-server:1.11.0`,
> `ghcr.io/spiffe/spire-agent:1.11.0` (`deploy/versions.bom.yaml`).

---

## 1. Identity model — one SPIFFE ID per service

Trust domain: **`hawk-eye`**. Every service gets exactly one identity:

```
spiffe://hawk-eye/ns/default/sa/<service>
```

…where `<service>` is the service's name from CONTEXT.md §7 (and its Kubernetes
`ServiceAccount`, `service-accounts.yaml`). Examples:

| Service | SPIFFE ID |
|---|---|
| backend | `spiffe://hawk-eye/ns/default/sa/backend` |
| serving | `spiffe://hawk-eye/ns/default/sa/serving` |
| postgres | `spiffe://hawk-eye/ns/default/sa/postgres` |
| tee-attestation | `spiffe://hawk-eye/ns/default/sa/tee-attestation` |
| pam-shim | `spiffe://hawk-eye/ns/default/sa/pam-shim` |
| governance-api | `spiffe://hawk-eye/ns/default/sa/governance-api` |
| … (all 23 services in CONTEXT.md §7) | … |

The full registration list is in `spire/registration-entries.yaml`.

### No shared / anonymous accounts (Part 19.3)
- **One identity per service.** Two services never share a SPIFFE ID, a cert, or a
  `ServiceAccount`. The Kubernetes `default` ServiceAccount is **never** used by a workload.
- **Humans are not services.** Service identities are never reused as admin logins; platform-admin
  access goes through PAM (`pam-shim`, PLATFORM-15) under a named human.
- This is the same control we monitor the *bank's* privileged users for — Hawk-Eye holds itself to
  it.

---

## 2. mTLS between internal services

- **Every internal hop is mutual TLS.** Both client and server present a cert and verify the
  peer's — there is no plaintext listener across a zone boundary (PLATFORM-10).
- **Authorization is by SPIFFE ID, not IP.** A reachable network path is not enough; the caller's
  SPIFFE ID must be on the callee's allow-list (matches the PLATFORM-10 §3 inter-zone edges).
- **Short-lived, auto-rotated.** On the real fabric SPIRE issues short-TTL X.509-SVIDs that rotate
  automatically; nothing relies on a long-lived static key (IAM likewise uses roles, no long-lived
  keys — `infra/terraform/modules/iam/`, owned by the Terraform workstream).

---

## 3. Local dev path (REAL today) — `gen-certs.sh`

For the local compose/k8s stack we don't run a SPIRE control plane; instead `gen-certs.sh` mints a
dev CA and one mTLS leaf per service, each carrying its SPIFFE ID in the **SAN URI** — the same
identity SPIRE will later issue.

```bash
./gen-certs.sh            # dev CA (once) + a cert per service in ./certs/
FORCE=1 ./gen-certs.sh    # rebuild everything
DAYS=825 ./gen-certs.sh   # override leaf validity (default 365d)
```

Output (in `./certs/`, **gitignored** — keys are never committed):

```
certs/
  ca/ca.crt  ca.key                         # dev CA
  <service>/<service>.crt                   # leaf (serverAuth + clientAuth)
  <service>/<service>.key                   # private key (chmod 600, gitignored)
  <service>/<service>.bundle.crt            # leaf + CA chain
```

The script is **idempotent** (re-running reuses the CA and existing certs) and **runs with plain
openssl** — no SPIRE, no network. Verify a cert's identity:

```bash
openssl x509 -in certs/backend/backend.crt -noout -text | grep -A1 'Subject Alternative Name'
#   URI:spiffe://hawk-eye/ns/default/sa/backend, DNS:backend, ...
openssl verify -CAfile certs/ca/ca.crt certs/backend/backend.crt   # -> OK
```

> The dev CA is a **demo convenience only**; it is not a trust anchor for anything real and its key
> never leaves the developer's machine / is never committed.

---

## 4. Real-fabric swap — SPIRE server + agent

In production the dev CA is replaced by **SPIFFE/SPIRE** with **no change to the identities**:

| Dev (today) | Real fabric (SPIRE) |
|---|---|
| `gen-certs.sh` mints static leaf certs | **SPIRE Server** is the CA / issuer (`spire/server-statefulset.yaml`) |
| Identity in cert SAN URI | **SPIRE Agent** attests the workload and hands it an **X.509-SVID** (`spire/agent-daemonset.yaml`) |
| 1-year leaf | Short-lived SVID, auto-rotated (minutes/hours) |
| Manual per-service files | **Registration entries** map each `ServiceAccount` → SPIFFE ID (`spire/registration-entries.yaml`) |
| `openssl verify` against dev CA | Peers trust the SPIRE trust bundle; mTLS via the Workload API / SDS |

Swap steps:
1. Deploy the SPIRE server (StatefulSet) + agent (DaemonSet) — `spire/`.
2. Apply the registration entries (one per service SPIFFE ID).
3. Point each workload's mTLS at the SPIRE Workload API (or Envoy SDS) instead of the files in
   `./certs/`.
4. Decommission the dev CA. Identities (`spiffe://hawk-eye/ns/default/sa/<service>`) are unchanged,
   so service-to-service authorization rules carry over verbatim.

See `spire/` for the SCAFFOLD manifests.

---

## 5. Files in this directory

| File | What |
|---|---|
| `gen-certs.sh` | dev CA + per-service mTLS certs with SPIFFE SAN URIs (REAL, idempotent) |
| `service-accounts.yaml` | one Kubernetes `ServiceAccount` per service (least-privilege, no shared accounts) |
| `spire/` | SPIRE server/agent manifests + registration entries (SCAFFOLD; real-fabric swap) |
| `certs/` | generated dev material — **gitignored**, never committed |

> Related: PLATFORM-10 (`security/zero-trust-policy.md`) consumes these identities for per-hop
> authn; `infra/terraform/modules/iam/` (Terraform workstream) carries the cloud IAM least-privilege
> roles — referenced here, not authored here.
