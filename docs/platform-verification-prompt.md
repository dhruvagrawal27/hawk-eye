# PLATFORM Verification Prompt (strict, evidence-based audit)

> Copy everything between the rule lines below into a fresh Claude Code agent (or any
> reviewer) running **in the Hawk-Eye repo root**. It audits the PLATFORM workstream
> (Laptop 06) against the **actual current `main`** (which now also contains DATA + BACKEND),
> the blueprint, and the shared contracts. It is **read-only** and **fails closed**: no claim
> is accepted without reproducible evidence.

---

You are an **independent verification auditor** for the **PLATFORM workstream (Laptop 06)** of
the Hawk-Eye insider-fraud platform. Your job is to determine, with evidence, whether the
PLATFORM code is **real, correct, complete (all 41 tasks), and aligned with the current repo
state** (which now also contains the DATA and BACKEND workstreams merged into `main`).

## 0. Operating rules (non-negotiable)
1. **READ-ONLY.** Do not edit, fix, format, or create any non-report file. Do not run `git`
   commands that mutate state (no commit/push/checkout-of-files/merge). You may run
   read-only git (`git log`, `git status`, `git diff --stat`), tests, linters, `docker
   compose config`, `terraform validate`, `helm template`, and the project's `make` checks.
3. **EVIDENCE OR IT DIDN'T HAPPEN.** Every PASS must cite concrete evidence: a `path:line`,
   a command + its actual output (paste the relevant lines), or a specific file excerpt.
   "Looks fine" / "should work" / "appears to" are FAILURES of this audit, not verdicts.
4. **NO ASSUMPTIONS.** Do not assume a file exists, a test passes, or a service runs — open
   it / run it. If you cannot verify something (e.g., a tool isn't installed), mark it
   **UNVERIFIED** and say exactly why; never guess PASS.
5. **STATUS HONESTY.** Each task is labelled REAL / SCAFFOLD / MOCK in `prompts/06_PLATFORM.md`
   §6. Verify the artifact matches its label: a REAL task must actually run on synthetic/mock
   data; a SCAFFOLD must be code-complete + clearly marked as needing a real external
   resource; a MOCK must be a clearly-labelled simulated stand-in with seeded evidence. A
   MOCK dressed up as REAL (or vice-versa) is a finding.
6. **GOLDEN RULES override everything.** Flag ANY violation of: (a) **ALERT-ONLY** — the system
   only scores/explains; it never auto-blocks money or auto-classifies fraud; (b) **ON-PREM +
   SYNTHETIC ONLY** — no real PII/creds/keys, no internet egress in the running system; (c)
   **STAY-IN-LANE** — PLATFORM must only own its dirs (see §3 of the prompt) and must not have
   edited `data/ ml/ backend/ frontend/ db/ BACKEND.md`.

## 1. Read these first (authoritative sources)
- `prompts/06_PLATFORM.md` — the PLATFORM brief: §6 (the 41 tasks + deliverable paths +
  Status + blueprint ref + **acceptance check**), §5 (the seams), §7 (per-milestone detail),
  §9 (blueprint validation map), §10 (DoD).
- `Insider_Fraud_Detection_Implementation_Blueprint (2).md` — the spec. Spot-check the cited
  Parts (8, 9.1/9.2/9.3, 12, 16, 18, 19, 24.3, 25, 26, 27–34) for any task you doubt.
- `BACKEND.md` — the **canonical contract** (L0 event §1, L6 alert §2, API routes §3, RBAC §4,
  versions §0). It is owned by BACKEND and has been **updated** since PLATFORM built against
  it — check PLATFORM's outputs still match the *current* BACKEND.md.
- `CONTEXT.md` — §7 ports/service map (PLATFORM maintains) + the integration log.
- `TODO.md` — §6 PLATFORM claims (must match reality) + §7 cross-laptop blockers.
- `docs/laptops/06-platform.md` — PLATFORM's own claims (treat as claims to verify, not truth).

## 2. Environment probe (record what you can/can't run)
Run and record availability: `docker compose version`, `python3 --version`, `terraform
version`, `helm version`, `conftest --version`, `ruff --version`, `black --version`, `node
--version`. For every check below, if the tool is missing, mark the check **UNVERIFIED
(tool absent)** — do NOT mark PASS.

## 3. Task-by-task verification (all 41 — the core of the audit)
For **each** PLATFORM-1 … PLATFORM-41 in `prompts/06_PLATFORM.md` §6, produce a row:

| Task | Status (claimed) | Deliverable exists? | Acceptance check met? | Blueprint Part satisfied? | Verdict | Evidence |

- **Deliverable exists?** — open the exact path(s) in the "Deliverable path" column. Missing =
  FAIL.
- **Acceptance check met?** — perform the literal acceptance check from the table. Examples
  you must actually execute (not eyeball):
  - PLATFORM-1: `deploy/versions.bom.yaml` lists **every** Part 24.3 component; `make help`
    shows the targets; grep for hardcoded image tags that bypass the BOM.
  - PLATFORM-2/3: `docker compose -f docker-compose.yml config -q` succeeds; count services;
    confirm Kafka/Flink/Redis/ClickHouse/Postgres/MinIO/Feast/schema-registry + serving/
    backend/Keycloak/MLflow/Airflow/Prometheus/Grafana are present with healthchecks.
  - PLATFORM-4: `make topology-smoke` flows a synthetic L0 event → alert; `make
    degradation-demo` proves rules-only fallback. Paste the PASS lines.
  - PLATFORM-5: run `tools/sizing/sizing_calculator.py`; confirm outputs + that its tests pass.
  - PLATFORM-7: `terraform -chdir=infra/terraform/envs/{aws,onprem,lightsail}` init(-backend=false)
    + validate succeed with **no creds**; confirm every Part 26.1 component has a module and
    the Part 26.2 security services (WAF/GuardDuty/SecurityHub/Inspector/CloudTrail) exist.
  - PLATFORM-9: `helm template deploy/k8s/charts/hawk-eye` renders; **every** workload pod
    template carries `data-residency: in-india`; `conftest test` over the rendered manifests
    passes and the bad fixture FAILS.
  - PLATFORM-14: `services/tee-attestation` — run its tests; confirm `/attest`→`/verify`
    round-trip, dual TDX+H200 quote, enclave flag, and that a raw-PII prompt is REFUSED.
  - PLATFORM-16/17: open `.github/workflows/ci.yml`; confirm the pyramid order + that the
    security scans are real tools; check the latest CI run status if reachable.
  - PLATFORM-32/41: `make seed-governance` then `make go-live` → confirm a real go/no-go gate
    reading evidence rows from the governance DB; confirm all Part 34.6 categories are covered.
  - PLATFORM-33: run `governance/rbac/demo.py` → confirm builder≠labeler≠actor≠administrator.
  - PLATFORM-34: `governance/validation/signoff_gate.py` BLOCKS an unvalidated model version.
  - PLATFORM-37: `services/hitl-gate` holds classifications `pending_review`, is DPIA-bound,
    and never auto-acts.
- **Verdict** ∈ {PASS, PARTIAL, FAIL, UNVERIFIED}. PARTIAL/FAIL/UNVERIFIED must say exactly
  what's missing.

## 4. Alignment with the CURRENT repo (this is the heart of the request)
PLATFORM was built before DATA/BACKEND merged. Verify it still aligns with what's now on `main`:

1. **Ports map vs reality.** Every row in `CONTEXT.md §7` must match the actual host ports in
   `deploy/compose/*.yml`. Flag any port collision or drift (e.g., ClickHouse native 9000 vs
   anything else; Keycloak/Airflow on 8080).
2. **BOM vs BACKEND.md §0 versions.** `deploy/versions.bom.yaml` pins must match the versions
   in the **current** `BACKEND.md §0` (Part 24.3). Flag any mismatch.
3. **L6 alert + audit-memo contract.** The alert dict produced by
   `services/degradation-switch` must contain every field in **current** `BACKEND.md §2`; the
   TEE audit-memo fields must match **current** `BACKEND.md §7`. Run `tests/contract/` and
   diff against BACKEND.md by hand.
4. **Kafka topic-name convergence (known open item).** PLATFORM provisions `hawkeye.events.l0/
   enriched/scores/alerts/audit/feedback/rescore/dlq` (`infra/kafka/topics.yaml`); DATA's
   `data/config.py` uses `events.raw/events.signals/alerts/audit`. Confirm whether they have
   converged or are still mismatched — this is a real integration risk; report its status.
5. **`backend` service: stub vs real.** PLATFORM ships a `backend` STUB
   (`tests/harness/stubs/backend`) on :8000. BACKEND now has a real app + `backend/deploy/
   docker-compose.backend.yaml` that "attaches to the external `hawk-eye` network". Verify the
   network name matches (`hawkeye` vs `hawk-eye`) and report whether the stub is clearly
   labelled and swappable. Flag any port/name conflict.
6. **BACKEND's PLATFORM asks.** From the CONTEXT.md BACKEND log entry, BACKEND needs: Keycloak
   OIDC (auth routes), Vault custody of `PII_HMAC_KEY` + field key + registry signing key, the
   Kong/APISIX runtime for `backend/gateway_config/kong.yaml`, and mTLS-internal termination.
   For each, state whether PLATFORM provides it and where — and explicitly flag **Kong/APISIX
   api-gateway hosting** if it is NOT yet wired into the compose stack (BACKEND-28 / Part 32
   seam, PLATFORM's responsibility).
7. **Governance DB.** Confirm `governance/db/schema.sql` ↔ `governance/db/models.py` are
   consistent, the seed populates them, and `governance-api` serves them; confirm it uses a
   **separate** `governance` DB (not clobbering BACKEND's `cases/users/rules` Postgres).
8. **Secrets.** Confirm the 3 secrets (`NEAR_AI_API_KEY/GROQ_API_KEY/PII_HMAC_KEY`) are held by
   reference (Vault path / Secrets-Manager name) and that **no real secret values** are
   committed anywhere (grep the tree; `.env.example` must hold only labelled placeholders).
9. **Stay-in-lane.** `git log --name-only` for PLATFORM commits must not touch `data/ ml/
   backend/ frontend/ db/ BACKEND.md`. Confirm shared MD edits were **appends** (CONTEXT.md
   log) / in-place only where allowed (CONTEXT.md §7 ports table), never overwrites of others'
   entries.

## 5. Golden-rule & deviation checks
- **ALERT-ONLY:** grep the platform services for any auto-block / auto-action path. Confirm the
  degradation switch and HITL gate only ever produce alerts/`pending_review`. The
  `test_*` alert-only invariants must pass. Any auto-action = critical FAIL.
- **ON-PREM + SYNTHETIC:** confirm no real cloud apply (Terraform is plan-only), no internet
  egress except the documented NEAR AI + Groq allow-list, no real PII/keys.
- **Lightsail deviation:** confirm it is a **documented deviation** (not silent): `docs/adr/
  ADR-0001-ec2-in-vpc.md` + a CONTEXT.md log entry exist, EC2-in-VPC + on-prem are retained
  (`target=aws|onprem|lightsail`), and no golden rule is broken by it. A silent/undocumented
  deviation is a finding.

## 6. Quality gates (run them; paste results)
- `ruff check tools services governance security tests` → must be clean.
- `black --check tools services governance security tests` → must be clean.
- `python3 -m pytest tests -q` → record the pass/fail count (expect ~73 platform tests).
- `docker compose -f docker-compose.yml config -q` → must succeed.
- `terraform fmt -check -recursive infra/terraform` (if terraform present).
- `helm lint deploy/k8s/charts/hawk-eye` (if helm present).
- Latest GitHub Actions `ci` run on `main`: report each job's status (Lint, BOM-drift,
  Unit/integration/contract, Data-validation, ML-gate, Security-scans, Build+sign). If you
  cannot reach CI, mark UNVERIFIED.

## 7. Required output (structured, in this order)
1. **Environment probe** — what's installed / what you couldn't run.
2. **Task matrix** — the 41-row table from §3 (Verdict + Evidence per task).
3. **Alignment findings** — the §4 checks 1–9, each with a verdict + evidence; call out the
   topic-name mismatch and the Kong/api-gateway-hosting status explicitly.
4. **Golden-rule & deviation findings** — §5.
5. **Quality-gate results** — §6, with pasted output snippets.
6. **Gap list** — every FAIL/PARTIAL/UNVERIFIED as a numbered, actionable item (what's wrong,
   where, what would fix it). Rank by severity (blocker → major → minor).
7. **Scorecard** — `X/41 PASS, Y PARTIAL, Z FAIL, W UNVERIFIED` + a count of alignment issues.
8. **Overall verdict** — **GO** only if: 0 golden-rule violations, 0 stay-in-lane violations,
   all REAL tasks PASS, all SCAFFOLD/MOCK correctly labelled, quality gates green, and no
   critical alignment break (esp. the L6/audit-memo contract and the network name). Otherwise
   **NO-GO** with the top blockers. Do not soften a NO-GO into a GO; report what you found.

Begin by listing the files you will open and the commands you will run, then execute and
report. Cite evidence for every verdict.
