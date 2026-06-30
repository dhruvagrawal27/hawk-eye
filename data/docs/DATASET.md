# Hawk-Eye Dataset & Schema — Explained From Zero

> Read this once and you can answer any "what's the data?" question. No prior knowledge assumed.

---

## 1. The one-paragraph answer (say this if someone asks)

> "We don't use real bank data — it doesn't exist publicly and it's too sensitive. Instead we **manufacture** realistic, **labelled** employee-behaviour data with a **simulator** that models a bank's staff doing normal work, and secretly injects **12 known insider-fraud schemes** with the ground-truth answer attached. Every action — a login, a payment, a database read — is turned into one standard record called an **L0 event**. That stream of L0 events is the dataset everything else (the ML models, the rules, the dashboard) is built on. We also wire in 6 public benchmark datasets for prototyping."

That's it. The rest of this doc is the detail behind that paragraph.

---

## 2. What "the dataset" actually is

There are **two sources**, used for different jobs:

| Source | What it is | Why |
|---|---|---|
| **A. Synthetic simulator** (primary) | Code that *generates* a fake bank's activity — employees, their daily work, and injected fraud — with the correct fraud/not-fraud label on every record | Real insider-fraud data is private and rare. We need labelled examples to build & test the system, so we make them. |
| **B. Public benchmarks** (prototyping only) | 6 well-known open datasets (CERT, IEEE-CIS, etc.) | To prototype/sanity-check models before real bank data is wired in. **Not** production-quality for *this* bank. |

**Important honesty line:** *No drop-in pre-trained model or real dataset exists for the bank.* The production signal will eventually be the bank's own telemetry + the synthetic library + analyst feedback. Today, locally, it's the simulator + public sets.

---

## 3. THE SCHEMA — what it is, where it lives, how to use it

### 3a. What a "schema" is (plain version)
A **schema** is the agreed *shape* of every record — the list of fields and their types — so that every part of the system (the simulator, the rules engine, the ML, the database, the dashboard) reads and writes data **the same way**. Think of it as the column headers + rules for one giant spreadsheet that everyone shares. Our schema is called **L0** ("Layer 0 — the unified event model").

### 3b. The shape: one event = 5 groups of fields
Every single thing that happens (a login, a payment, a DB read) becomes **one L0 event** with five groups:

| Group | Answers | Example fields |
|---|---|---|
| **actor** | *Who did it?* | `employee_id`, `role`, `dept`, `branch`, `tenure_days`, `manager_id`, `peer_group`, `privileged_flag`, `leaver_flag` |
| **action** | *What did they do?* | `verb` (e.g. `approve_payment`), `channel` (cbs/swift/iam/db…), `maker_checker` |
| **object** | *On what?* | `account_id`, `beneficiary_id`, `table`, `entitlement_id`, `instrument`, `amount`, `currency` |
| **context** | *When / where / how?* | `ts` (UTC time), `src_ip`, `device`, `geo`, `session_id`, `layer` (app/db), `is_off_hours`, `host` |
| **linkage** | *What does it connect to?* | `swift_ref`, `cbs_ref`, `app_txn_id`, `db_write_id`, `maker_id`, `checker_id`, `customer_account` |

`linkage` is the clever bit — it's how we join a SWIFT message to its CBS posting, or a maker to a checker, to catch fraud that lives *in the seam* between systems.

### 3c. WHERE the schema lives (file locations)
All under [`data/schemas/`](../schemas/):

| File | What it is | Use it when… |
|---|---|---|
| **`l0_event.py`** | The schema **in Python** (dataclasses) + a `validate_event()` checker. **This is the source of truth.** | You're writing Python and want to create/validate events |
| **`l0_event.avsc`** | The same schema in **Avro** (JSON format) | Kafka/streaming serialization, schema registry |
| **`l0_event.proto`** | The same schema in **Protobuf** | High-performance streaming / code-gen in other languages |
| **`sample_event.json`** | One **filled-in example** event you can eyeball | You just want to *see* what a record looks like |
| **`label.py`** | The separate **label** record (is_fraud, scenario_id, …) | Labels are kept apart from events on purpose (see §6) |

### 3d. HOW to access it (3 ways, easiest first)

**Way 1 — just look at one example (no coding):** open [`data/schemas/sample_event.json`](../schemas/sample_event.json). That's exactly one L0 event.

**Way 2 — in Python (the normal way):**
```python
from data.schemas import L0Event, Actor, Action, validate_event, SAMPLE_EVENT

# see the canonical example
print(SAMPLE_EVENT)

# build one
ev = L0Event(
    event_id="evt_demo01", ts="2026-06-30T02:14:07Z",
    actor=Actor(employee_id="EMP-7f3a", role="ops_maker", privileged_flag=False),
    action=Action(verb="create_beneficiary", channel="cbs", maker_checker="maker"),
)
print(ev.to_dict())            # nested dict matching the schema
print(validate_event(ev.to_dict()))   # [] means valid; a list of strings means errors
```

**Way 3 — read the raw schema files:** `data/schemas/l0_event.avsc` (Avro) or `.proto` (Protobuf) if you're integrating a non-Python system.

> **Who owns it:** the DATA workstream owns the L0 schema; BACKEND, ML, DATABASE and FRONTEND all *read* it. The same definition also appears in [`BACKEND.md`](../../BACKEND.md) §1 so every laptop agrees on it.

---

## 4. How the synthetic data is generated (the simulator)

Run by `python -m data.sim.cli`. Three layers:

1. **Population** (`data/sim/population.py`) — creates N fake employees with a role, department, branch, tenure, manager, peer group, and a "privileged" flag. The 10 roles: **teller, ops_maker, ops_checker, dba, sysadmin, loan_officer, appraiser, trader, aml_analyst, vendor_admin**.
2. **Normal behaviour** (`data/sim/normal_behaviour.py`) — each role does realistic daily work on realistic schedules (tellers in branch hours, DBAs at night, makers & checkers pairing on payments, analysts clearing alerts). This is the "haystack."
3. **Fraud injectors** (`data/sim/scenarios/`) — for a *rare* few employees, it secretly weaves in one of **12 fraud schemes** (the "needles"), tagging every fraudulent event with the truth.

Output: two files per run — **events** (the L0 stream) and **labels** (the answers), each as **Parquet** (for analysis) and **JSONL** (human-readable), under `data/out/<run>/`.

---

## 5. The 12 fraud schemes ("typologies")

Each is a real insider-fraud pattern from the blueprint. **Fast lane** = catchable in real time; **slow lane** = surfaces over weeks (credit/vendor fraud).

| # | Typology | Lane | The tell-tale signal |
|---|---|---|---|
| 1 | beneficiary_then_approve | fast | new payee created → high-value payment approved by the same maker/checker |
| 2 | dormant_takeover | fast | a dead account suddenly reactivates → drains |
| 3 | swift_without_cbs | fast | a SWIFT message with **no matching CBS book entry** (the PNB scam) |
| 4 | suspense_lapping | fast | the same person posts *and* reconciles aging suspense items |
| 5 | privilege_self_grant | fast | short-lived admin right granted right around a fraudulent approval |
| 6 | bulk_exfil_resignation | fast | huge data download during someone's notice period |
| 7 | maker_checker_ring | fast | the same two people always approve each other (collusion) |
| 8 | rogue_trader | fast | never takes leave + cancel/rebook trades + mismarked positions |
| 9 | fake_vendor | slow | vendor's address = an employee's address; round/sequential invoices |
| 10 | ghost_employee_payroll | slow | a "staff" payee with no tax footprint / duplicated bank details |
| 11 | alert_suppression | slow | one AML analyst clears a suspiciously high share of alerts |
| 12 | ghost_loan_appraisal | slow | the appraiser *is* the borrower; money goes to a non-sanctioned account |

---

## 6. The labels (the "answers") — and why they're separate

A **label** says whether an event is fraud and which scheme it belongs to: `is_fraud`, `scenario_id`, `actor_id`, `ring_id`, `lane`, `label_source`. They live in `data/schemas/label.py` and the label store `data/labels/label_store.py`.

**Why separate from events?** If the fraud flag lived *inside* the event, the model would "cheat" by reading the answer — that's called **leakage**. So events carry no label; labels are joined by `event_id` only at training time.

**Four label sources** (real systems blend these):
1. **gold** — confirmed historical cases (seeded mock here; real ones are confidential)
2. **weak** — auto-labels from rule hits (programmatic / Snorkel-style)
3. **synthetic** — the simulator's ground truth (what we mostly use today)
4. **EDD feedback** — every investigator decision (fraud / false-positive / inconclusive) flows back as a new label (this is how the system keeps learning)

---

## 7. The public benchmark datasets (prototyping only)

Loaders in `data/datasets/loaders/`. Each maps the public set into our L0 shape and documents its purpose + caveats:

| Loader | Dataset | Used to prototype… | Caveat |
|---|---|---|---|
| `cert.py` | CMU-SEI CERT Insider Threat | the insider/behaviour layers | synthetic benchmark |
| `ieee_cis.py` | IEEE-CIS Fraud (Vesta) | the tabular gradient-boosting model | card fraud, not insider |
| `ulb.py` | ULB Credit-Card Fraud | extreme class-imbalance handling | tiny fraud rate |
| `paysim.py` | PaySim mobile-money | pipeline scale/throughput | **balance columns leak — don't train on them** |
| `elliptic.py` | Elliptic Bitcoin graph | the graph/collusion layer | crypto, not banking |
| `spedia.py` | SPEDIA / Amazon FDB | broader benchmarking | aggregated |

---

## 8. The numbers (a real run you can quote)

`python -m data.sim.cli --employees 1000 --days 30` (seed 1405) produced:

- **118,518 events** total
- **57 fraud-labelled events** → **0.048%** of events (deliberately rare, like real fraud)
- **14 fraudulent employees** out of 1,000 → **1.4%** of staff
- Split **35 fast-lane / 22 slow-lane**, all 12 typologies present
- Most common actions: `login`, `cash_withdrawal`, `cash_deposit`, `balance_enquiry`, `approve_payment`, `create_beneficiary`, `initiate_payment`, alert open/clear/escalate
- Channels: mostly `cbs`, plus `dlp`, `treasury`, `iam`, `db`, `hr`, `swift`

Scale it up with `--employees` and `--days` (production target ≈ 18 months of data). It's **deterministic**: same seed → identical output.

---

## 9. How to access / run everything (copy-paste)

```bash
# from the repo root
python -m data.sim.cli --employees 1000 --days 30   # generate -> data/out/<run>/{events,labels}.{parquet,jsonl}
python -m data.tests.run                            # run all 97 data tests

# peek at the generated data in Python
python -c "import pandas as pd, glob; f=sorted(glob.glob('data/out/**/events.parquet',recursive=True))[-1]; print(pd.read_parquet(f).head())"
```

No special install needed — it runs on `numpy` + `pandas` + `pyarrow`. (Kafka/Flink/Feast/Redis/ClickHouse are optional; the code falls back to local files/memory without them.)

---

## 10. Splits, leakage, governance (one-liners)

- **Splits** (`data/datasets/splits.py`): always **by time** (train on the past, test on the future) and **entity-disjoint** (the same employee never appears in both train and test). Random splits are rejected. Leaky columns are auto-detected and dropped.
- **Catalog & classification** (`data/governance/`): every L0 field is documented; PII/PAN fields are tagged so they get masked.
- **Quality** (`data/governance/quality/`): completeness/validity/freshness/range checks catch bad data at ingestion.
- **Lineage** (`data/lineage/`): every dataset gets a content hash so any model/alert can be traced back to the exact data it used.

---

## 11. FAQ — if someone asks you…

- **"Is this real customer data?"** → No. 100% synthetic + public benchmarks. No real PII anywhere. IDs like `EMP-7f3a`, `ACCT-4d22` are fake.
- **"Where's the schema?"** → `data/schemas/l0_event.py` (Python source of truth), plus `.avsc`/`.proto` mirrors and `sample_event.json` to look at. Also documented in `BACKEND.md` §1.
- **"How do I see a record?"** → open `data/schemas/sample_event.json`, or run the simulator and read `data/out/<run>/events.jsonl`.
- **"What's an L0 event?"** → one standardized record for any action, with 5 field groups: actor / action / object / context / linkage.
- **"How is fraud labelled?"** → the simulator injects 12 known schemes and tags every fraudulent event with the truth (kept in a separate label file to avoid leakage).
- **"How much fraud is in it?"** → deliberately rare: ~0.05% of events, ~1–1.5% of employees — matching real-world imbalance.
- **"Can I trust the public datasets?"** → for prototyping only; they're not this bank's distribution. Production signal = our own telemetry + synthetic + analyst feedback.

---

*Owner: DATA workstream. Source of truth for the schema is `data/schemas/l0_event.py`. This doc is a human explainer — when in doubt, the code + `BACKEND.md` §1 win.*
