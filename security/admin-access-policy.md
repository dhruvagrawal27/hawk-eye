# Platform Admin Access Policy (PLATFORM-15)

> **Purpose.** Define how a human platform administrator obtains, uses, and is held accountable for
> privileged access to Hawk-Eye: all admin access is **brokered through PAM** (the `pam-shim` mock,
> :8091), **session-recorded**, **least-privilege**, **named** (never shared/anonymous),
> **four-eyes** for privileged change, and **audited to the WORM log** ("watch the watchers").
>
> **Blueprint:** Part 9.3 (privileged access management), Part 19.3 (PAM session recording,
> no shared accounts, least privilege). **Task:** PLATFORM-15. **Status:** MOCK — `pam-shim`
> simulates the broker; the real swap is **CyberArk / BeyondTrust** (§7).
>
> **Ties to:** PLATFORM-33 (SoD personas: builder / labeler / actor / administrator) and
> PLATFORM-10 (the management zone is reachable only through PAM).

---

## 0. Golden-rule alignment

- **ALERT-ONLY.** Admin access governs *operating* the platform; an admin never "clears" or
  auto-actions a fraud alert outside the dual-control investigation workflow. Privileged actions
  change infrastructure, not case dispositions.
- **NO SHARED / ANONYMOUS ACCOUNTS.** Hawk-Eye exists to catch privileged-user fraud; its own
  admins are held to the same bar. Every privileged action is attributable to a **named human**.
- **WATCH-THE-WATCHERS.** Every administrative action is recorded and written to the immutable
  (WORM) audit log; the people with the most power are the most observed.

---

## 1. Principles

1. **PAM-brokered, always.** A platform admin never connects directly to a host, container, or
   admin endpoint. They open a **PAM session** (`pam-shim` `POST /sessions/start`) stating *who*,
   *what role*, and *why* (justification / ticket ref), and every privileged command flows through
   the broker (`POST /sessions/{id}/command`), which checks least-privilege before allowing it.
2. **Named identity only — no shared/anonymous accounts.** Accounts such as `root`, `admin`,
   `shared`, `service`, `svc`, `ops`, or an empty principal are **forbidden** and rejected by the
   broker (`FORBIDDEN_ACCOUNTS`, `services/pam-shim`). Access is always tied to a named human plus
   their SoD persona.
3. **Least privilege.** Each role carries the smallest command allow-list needed for its duty
   (§3). There is **no standing super-admin**; broad power is assembled, time-boxed, and
   four-eyes-gated, not held permanently.
4. **Session recording.** Every PAM session is recorded (a session-recording stub in the mock,
   `worm://pam-recordings/<session>.cast`; a real terminal/keystroke/screen recording in the
   CyberArk/BeyondTrust swap). Recordings are immutable and retained per policy.
5. **Four-eyes for privileged change.** Any *change-class* privileged action (deploy config,
   rotate a secret, update a policy, restore data, fail over) requires a **second approver**
   distinct from the actor — segregation of the requester and the approver.
6. **Just-in-time, time-boxed.** Sessions are short-lived and explicitly ended
   (`POST /sessions/{id}/end`); access is not left open. (Real PAM: JIT elevation + auto-expiry.)
7. **Watch-the-watchers / immutable audit.** Every session start, every command (allowed *and*
   denied), and every session end is written to the WORM audit log (`hawkeye.audit`) — admin
   activity is itself a first-class auditable, alertable event.

---

## 2. The management path (how an admin actually reaches a workload)

```
named human ──(OIDC: Keycloak, SoD persona)──▶ pam-shim (:8091)
     │                                              │  least-privilege check + record
     │                                              ▼
     └────────────────────────▶  management zone  ──▶  target workload (app/compute/governance)
                              (PLATFORM-10 zone, PAM-gated)
```

- The **management zone** (PLATFORM-10 §2) is reachable for admin actions **only** through
  `pam-shim`; there is no direct admin route from a laptop to a workload.
- Admin authentication is the named human's **Keycloak** identity with the SoD `administrator`
  persona (PLATFORM-33); PAM adds the per-command least-privilege gate on top.

---

## 3. Least-privilege roles (mirror of `services/pam-shim`)

No role is a super-admin. Each role's command allow-list is enforced by the broker:

| Role | Allowed commands (least privilege) | Notes |
|---|---|---|
| `platform_admin` | `restart_service`, `view_logs`, `rotate_secret`, `scale`, `deploy_config` | change-class commands (`rotate_secret`, `deploy_config`) are four-eyes |
| `sre_oncall` | `restart_service`, `view_logs`, `scale`, `failover` | operational continuity; `failover` is four-eyes |
| `db_admin` | `backup`, `restore`, `view_schema` | `restore` is four-eyes; cannot read app secrets |
| `security_admin` | `rotate_secret`, `view_audit`, `update_policy` | `update_policy` is four-eyes; **separated from operators** |

Separation built in:
- The person who can **`update_policy`** (`security_admin`) is **not** the person who runs
  day-to-day **`deploy_config`** (`platform_admin`) — segregation of duties between *changing the
  rules* and *operating the system*.
- `db_admin` can move data but cannot rotate secrets or change policy.
- No single role can simultaneously deploy code, change security policy, and approve its own
  change.

**Change-class commands (require four-eyes):** `rotate_secret`, `deploy_config`, `update_policy`,
`restore`, `failover`. A session command of these types carries an approver field; the broker (real
PAM) records both the actor and a distinct approver, and refuses self-approval.

---

## 4. No shared / anonymous accounts (the anti-pattern this platform catches)

- The broker **rejects** any session whose `admin` principal is in the forbidden set
  (`root`, `admin`, `shared`, `service`, `svc`, `ops`, empty) — Part 19.3.
- Service-to-service identity is **not** an admin account: services use per-service SPIFFE IDs and
  Kubernetes `ServiceAccount`s (PLATFORM-11, `deploy/mtls/`), one per service, never shared, never
  used by a human.
- Break-glass is still **named**: a break-glass session uses a real person's identity with an
  elevated, time-boxed, four-eyes-approved role — not a generic emergency login.

---

## 5. Session recording & WORM audit ("watch the watchers")

- **What is recorded.** Session metadata (who / when / role / justification), every command and its
  allow/deny result, and a session recording artifact (keystroke/screen in real PAM; a
  `worm://pam-recordings/<id>.cast` stub in the mock).
- **Where it goes.** The immutable **WORM** audit log (`hawkeye.audit`, retention per Part 16/19).
  Records are write-once: an admin cannot edit or delete their own trail.
- **Observability.** Admin actions are exported as audit events; anomalous admin behavior
  (off-hours `rotate_secret`, repeated denials, self-grant attempts) is itself alertable — the same
  detections Hawk-Eye runs on bank insiders apply to its operators.
- **Integrity.** The audit chain is tamper-evident (hash-chained / WORM bucket in prod); the mock
  marks records `stub: true` but preserves the who/when/what shape the real store will keep.

---

## 6. Lifecycle

1. **Start** — `POST /sessions/start {admin, role, reason}` → named human, SoD persona, justification
   recorded; recording begins; shared/anonymous principals rejected.
2. **Act** — `POST /sessions/{id}/command {command, target}` → least-privilege check; change-class
   commands require a distinct approver (four-eyes); every command audited (allowed or denied).
3. **End** — `POST /sessions/{id}/end` → session summary + recording URI written to WORM; access
   revoked; nothing left standing.
4. **Review** — `GET /sessions` → audit view (who/when/what) for the security team and validators.

---

## 7. Real PAM swap (production)

The `pam-shim` is a **MOCK**. In production it is replaced by an enterprise PAM platform —
**CyberArk Privileged Access Manager** or **BeyondTrust Privileged Remote Access** — with **no
change to this policy's controls**:

| Mock control (`pam-shim`) | Real PAM equivalent |
|---|---|
| `POST /sessions/start` + justification | PAM session request + ticket/approval workflow (JIT elevation) |
| `worm://pam-recordings/<id>.cast` stub | Full session recording (keystroke, screen, command replay) |
| `ROLE_ALLOW` command allow-lists | PAM least-privilege command filtering / safe-list policies |
| `FORBIDDEN_ACCOUNTS` reject | Credential vaulting + brokering (no shared creds ever exposed) |
| four-eyes approver field | Dual-control / maker-checker approval enforced by PAM |
| WORM audit (`hawkeye.audit`) | PAM session vault + SIEM forwarding, immutable retention |

Swap steps: point admin auth at the PAM's connector, vault all privileged credentials in the PAM,
map the four roles (§3) to PAM safe-list policies, enable session recording + dual control, and
forward the PAM audit stream to the WORM store / SIEM. No golden rule changes; the demo's behavior
is identical.

---

## 8. Verification checklist (CI / review)

- [ ] No human ever has a direct (non-PAM) path to a workload (PLATFORM-10 management zone).
- [ ] Shared/anonymous principals (`root`/`admin`/`shared`/…) are rejected at session start.
- [ ] Each role's command set matches `services/pam-shim` `ROLE_ALLOW` (no standing super-admin).
- [ ] Change-class commands (`rotate_secret`/`deploy_config`/`update_policy`/`restore`/`failover`)
      require a distinct approver (four-eyes; no self-approval).
- [ ] Every session start/command/end is written to the WORM audit log.
- [ ] Service identities (SPIFFE/`ServiceAccount`) are never used as admin accounts.
- [ ] Roles map cleanly onto the SoD `administrator` persona (PLATFORM-33).
