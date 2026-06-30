# Hawk-Eye — Getting Started (read me first, no experience needed)

This guide assumes you know **nothing** about the project. By the end you'll understand what
Hawk-Eye is, see it working in a couple of minutes, and know where everything lives.

---

## 1. What is Hawk-Eye, in one paragraph

Hawk-Eye is a **fraud-detection system for a bank** that watches what the bank's **own
employees** do (not customers). Insider fraud — a teller draining a dormant account, an
officer approving a payment to a shell company they secretly own, two colleagues colluding to
bypass the "two people must approve" rule — is rare, slow, and hidden in millions of normal
actions. Hawk-Eye reads every employee action, scores how suspicious it is, **explains why**,
and shows the risky ones to a **human investigator** on a dashboard. The golden rule:
**it only raises alerts — it never freezes money or fires anyone by itself. A human always decides.**

Everything runs **locally on fake (synthetic) data** — there is no real bank, no real people,
no real money. It's a complete, working *demonstration* of how such a system is built.

---

## 2. The mental model (a conveyor belt)

Think of an airport security belt. A bag (an **employee action** — a login, a payment, a
database export) rides the belt through a series of scanners:

```
   employee action
        │
   ┌────▼─────────────────────────────────────────────────────────────┐
   │ L0  put every action into ONE common format (the "event")         │
   │ L1  hard rules: "new payee + huge amount + 2am" → flag             │
   │ L2  "is this weird for THIS person / their peers?" (no labels)     │
   │ L3  "does this look like past known fraud?" (learned from labels)  │
   │ L4  "is the SEQUENCE of actions odd over time?"                    │
   │ L5  "who is connected to whom?" (collusion rings, shell vendors)   │
   │ L6  combine all the above into ONE 0–100 risk score + reasons      │
   └────┬──────────────────────────────────────────────────────────────┘
        │
   a calibrated alert  (risk 87/100, "high", with plain-English reasons)
        │
   ┌────▼─────────┐     ┌──────────────────────────────────────────────┐
   │ Dashboard    │ ──▶ │ A human investigator reviews it, decides, and │
   │ (the "L7")   │     │ their decision teaches the system (feedback). │
   └──────────────┘     └──────────────────────────────────────────────┘
```

Two more parts wrap around the belt: an **AI assistant** that writes a short plain-English
story of *why* each alert fired (it explains, it never decides), and the **plumbing**
(databases, security, monitoring) that makes it run like a real bank system.

---

## 3. What's in the box (the 6 parts)

The project is split into 6 folders, each built as if by a separate team ("laptop"):

| Folder | Plain English | Tech |
|---|---|---|
| `data/` | Makes the fake bank data + turns raw actions into the common "event" format and useful features | Python |
| `ml/` | The **brain** — the L2–L6 scanners, the scoring, the explanations, the AI narrative | Python |
| `backend/` | The **control room** — the web API, the hard rules (L1), login/permissions, the audit log, regulator reports | Python (FastAPI) + a bit of Rust |
| `frontend/` | The **dashboard** the investigator looks at | React/TypeScript |
| `infra/`, `services/`, `tools/` | The **plumbing** — how to run everything together, security, monitoring, deployment | Docker, Terraform, Python |
| `db/` | (storage schemas — in this build, storage is provided by the plumbing above) | — |

There's also `docs/` (deeper documentation), `prompts/` (the original build briefs), and
`tests/` (proof everything works).

---

## 4. See it work in 2 minutes (the easiest path)

The fastest way to watch the "brain" detect fraud end-to-end, using only Python:

```bash
# from the project folder. One-time setup of the ML environment (Python 3.13):
python3.13 -m venv .mlvenv
.mlvenv/bin/python -m pip install -U pip
.mlvenv/bin/python -m pip install numpy pandas scikit-learn pyod lightgbm xgboost catboost shap torch torch_geometric mlflow evidently fairlearn featuretools onnxruntime openai jinja2 fastapi

# run the end-to-end demo:
.mlvenv/bin/python -m ml.demo
```

You'll see a synthetic fraud burst flow L0 → L2 → L3 → L5 → L6, end with a **risk 100/100
critical alert on a genuinely fraudulent employee**, print the **reasons**, and a short
**narrative** — then confirm the alert is *contestable* (has reasons) and *reproducible*.
That single command is the whole detection idea in miniature.

---

## 5. See the investigator dashboard

```bash
cd frontend
npm install          # one time (needs Node 22+)
npm run dev          # opens http://localhost:5173
```

The dashboard runs on **built-in mock data** (no backend needed) — a triage queue of alerts,
the entity-360 view, the explanation panel (SHAP reasons + the AI narrative + a graph of who's
connected to whom), and the investigator's review actions. This is "L7" — what a human uses.

---

## 6. Run the API (the control room)

```bash
python3.13 -m venv .bevenv
.bevenv/bin/python -m pip install -e 'backend/[dev]'
.bevenv/bin/python backend/run_api.py        # API on http://localhost:8000
# open http://localhost:8000/api/v1/docs for the interactive API explorer
```

Log in (synthetic users, password `hawk-eye`): `EMP-an01` (analyst), `EMP-co01` (compliance),
`EMP-au01` (auditor), etc. The API serves the ranked alert queue, full alert details with
reasons, the EDD disposition (an investigator's verdict that teaches the system), PII unmasking
(audited), and the regulator reports.

---

## 7. Run the *whole* thing together (the full experience)

This brings up the complete platform — Kafka, ClickHouse, Redis, Postgres, MinIO, the API,
serving, dashboards, monitoring — as ~26 connected services. **It needs Docker installed.**

```bash
make config     # validate the setup renders (no Docker needed)
make up         # bring the whole stack up (needs Docker; pulls images)
make ps         # see what's running
make down       # stop it
```

If you don't have Docker, paths 4–6 above already let you see every important piece working.

---

## 8. Prove it works (run the tests)

Each part has its own test suite. All green today:

```bash
.venv/bin/python  -m data.tests.run          # DATA   → 100 passed
.mlvenv/bin/python -m ml.tests.run            # ML     → 250 passed
cd backend && ../.bevenv/bin/python -m pytest # BACKEND→ 109 passed
cd frontend && npm test                       # FRONT  → 112 passed (+3 browser e2e)
.pfvenv/bin/python -m pytest tests -q -m "not perf and not chaos" --ignore=tests/ml  # PLATFORM → 73 + contract

# the adversarial "red-team" suite (tries to BREAK the safety rules):
.pfvenv/bin/python -m pytest tests/redteam/test_alert_only_and_secrets.py tests/redteam/test_contract_conformance.py
cd backend && ../.bevenv/bin/python -m pytest ../tests/redteam/test_rbac_sod_audit.py
```

> **Note for Macs:** the ML test runner runs each test file in its own process on purpose —
> PyTorch and LightGBM both ship a maths library (`libomp`) that crashes if loaded together in
> one long-running process. `python -m ml.tests.run` handles this for you.

---

## 9. How it actually works (a little deeper)

- **L0 — one common format.** Every action (from any source) becomes the same JSON "event":
  *who* (actor), *did what* (action), *to what* (object), *in what context* (time, device,
  location), and *links* (e.g. the SWIFT message ↔ the core-banking entry). See `BACKEND.md` §1.
- **L1 — rules.** Fast, hard-coded red flags and the "separation of duties" matrix (e.g. the
  same person must not both make and approve a payment). Explainable by definition.
- **L2 — unsupervised.** Learns each person's *normal* and flags deviations **relative to their
  peers** (not an absolute threshold — that's fairer and harder to game). Needs no labels.
- **L3 — supervised.** Once investigators have confirmed some fraud, a gradient-boosted model
  (LightGBM) learns the patterns and scores new events, with **SHAP** showing which features
  drove each score.
- **L4 — sequence.** Looks at the *order and timing* of actions (slow-burn schemes). Simple
  methods first; deep models only if they genuinely beat the simple ones.
- **L5 — graph.** Builds a network of employees, accounts, beneficiaries, devices, vendors and
  finds **collusion rings** and **shell vendors** that look fine individually.
- **L6 — fusion.** Combines all layers + the rules into **one calibrated 0–100 score** with
  **severity × confidence** and a single set of **reason codes** (so you get one alert per
  person, not ten).
- **The AI narrative.** A language model (running in a secure enclave, with all names replaced
  by tokens) writes a short factual story of the alert. If the AI is unavailable, a template
  writes it instead — **the dashboard never breaks**. The AI **only explains; it never decides**.
- **The feedback loop.** Every investigator verdict becomes a new label → the models retrain →
  the system gets better the longer it runs.

---

## 10. The non-negotiable rules (why you can trust it)

1. **Alert-only.** Nothing is ever auto-blocked or auto-classified. A human decides. *Enforced
   in code* (`ml/design/alert_only_contract.py`; the API only has a *block-request* a human raises).
2. **On-prem + synthetic only.** No real people, no real money, no cloud secrets. API keys are
   injected at runtime, never written in the code.
3. **Everything is contestable.** Every alert carries reason codes + a narrative, so the accused
   can challenge it (natural justice). An alert with no reasons is rejected.
4. **Watch the watchers.** Every sensitive action (who viewed whom, every unmask) is written to a
   **tamper-evident audit log** (hash-chained — edits are detectable).
5. **Fair.** Scoring is peer-relative; protected attributes are never used; the build *fails* if
   a fairness check trips.

---

## 11. What's real vs. pretend (honest limits)

- **REAL** — works fully on the synthetic + public data, locally: all of L1–L6, the dashboard,
  the API, the rules, fairness, the audit log, the regulator reports.
- **SCAFFOLD** — the code is complete but needs a real key/hardware to go *live*: the calls to
  the external AI providers (NEAR AI / Groq) and the secure-enclave attestation. Without keys,
  the system automatically falls back to the template narrative, so nothing breaks.
- **MOCK** — a stand-in for a human/legal/hardware step: e.g. the "independent model validator"
  sign-off is simulated. These are clearly labelled in the code.

See `docs/honest-limits.md` for the full list.

---

## 12. Glossary (every term in one line)

- **Insider fraud** — fraud committed by an employee, not an outside customer.
- **L0–L7** — the layers: L0 common event, L1 rules, L2 unsupervised, L3 supervised, L4 sequence,
  L5 graph, L6 fusion, L7 the dashboard/human.
- **UEBA** — User & Entity Behaviour Analytics; learning each person's normal to spot deviations.
- **Supervised / Unsupervised** — *supervised* learns from labelled examples of fraud;
  *unsupervised* needs no labels, just flags the unusual.
- **GBDT / LightGBM / XGBoost / CatBoost** — gradient-boosted decision trees; the workhorse models
  for this kind of tabular data.
- **SHAP** — a method that says *which features* pushed a score up or down (the "reasons").
- **GNN / GraphSAGE / XGB-Graph** — graph models that score how risky someone's *connections* are.
- **Calibration** — making a score mean what it says (a "70/100" really is ~70% likely).
- **Reason codes** — the structured evidence on an alert (`{source, code/feature, detail/contribution}`).
- **EDD disposition** — the investigator's verdict (fraud / false-positive / inconclusive) that
  becomes a training label.
- **RBAC** — Role-Based Access Control; who is allowed to do what.
- **SoD** — Separation of Duties; e.g. whoever builds models can't also label data or close their
  own alerts.
- **PII / tokenization** — Personally Identifiable Information; replaced by safe tokens
  (`EMP-7f3a`) before anything leaves the secure perimeter.
- **TEE / attestation** — Trusted Execution Environment; secure hardware that proves the AI ran
  untampered without exposing the data.
- **WORM audit** — Write-Once-Read-Many; an audit log that can't be secretly edited.
- **RBI / FMR / CRILC / EWS / TAT** — Indian banking-regulator terms: the central bank (RBI) and
  the fraud/credit reports and the 30-day turnaround time the system must meet.
- **Synthetic data** — realistic *fake* data generated by a simulator; no real people involved.
- **REAL / SCAFFOLD / MOCK** — status labels: works now / needs a real key-or-hardware / simulated stand-in.

---

## 13. Where to go next

- `README.md` — the project's index and the 6-workstream map.
- `BACKEND.md` — the exact data contracts (event shape, alert shape, API routes) everything agrees on.
- `CONTEXT.md` — the shared decision log across all parts (read the integration log at the bottom).
- `docs/` — deeper docs: `data-dictionary.md`, `detection-coverage-map.md`, `phasing.md`,
  `honest-limits.md`, `runbooks/ops-manual.md`, and the per-part logs in `docs/laptops/`.
- `Insider_Fraud_Detection_Implementation_Blueprint (2).md` — the full 34-part spec this is built from.
- `tests/redteam/` — the adversarial tests that try to break the safety rules.
