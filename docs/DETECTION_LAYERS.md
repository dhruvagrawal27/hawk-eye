# Hawk-Eye — Detection Layers (L0–L7): Design & Rationale

Hawk-Eye detects insider and privileged-user fraud in a bank by running every event through a **defence-in-depth funnel of complementary detectors** rather than a single model. A canonical **L0 event** (`data.schemas.l0_event`, produced by the synthetic simulator `python -m data.sim.cli` and normalized behind `ml/adapters/`) flows first through **L1 deterministic rules / BRE** (`backend/rules_engine/`, SoD and toxic-combo catalogue with four-eyes change control — the only non-ML layer). Events then fan out to the ML layers: **L2 unsupervised/UEBA** for cold-start novelty (`ml/layers/l2/`), **L3 supervised GBDT** as the precision event scorer (`ml/layers/l3/`), **L4 sequence/time-series** for low-and-slow session behaviour (`ml/layers/l4/`), and **L5 graph/relational** for collusion rings (`ml/layers/l5/`). Their per-layer scores plus rule hits are combined by **L6 risk fusion** — a *transparent* stacked meta-learner over `LAYER_COLUMNS = ("L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph")` (`ml/layers/l6/`, served via `backend/fusion/`) — into one calibrated **0–100 score with reason codes**, which surfaces to the **L7 investigator dashboard** for a human EDD decision. Critically, Hawk-Eye is **ALERT-ONLY**: it scores and explains; it never auto-blocks money (`docs/detection-coverage-map.md`; model version `fusion-2026.2.0`).

```
                                 (fan-out to ML detectors)
                          ┌───────────────────────────────────────────┐
 L0 event                │  L2 unsupervised  ─┐                        │
 (l0_event / simulator)  │  L3 GBDT scorer   ─┤                        │
        │                │  L4 sequence      ─┼─► L6 fusion  ──► L7     │
        ▼                │  L5 graph         ─┘   (0–100 +      dashboard
   L1 rules / BRE  ──────┤  (L1 rule hits) ──►    reason codes)  (human EDD,
   (SoD, toxic combos)   │                        calibrated       alert-only)
                          └───────────────────────────────────────────┘
```

| Layer | Technique | Catches |
|---|---|---|
| **L1 — Rules / BRE** | Deterministic rules / CEP (SoD matrix, toxic combos; not ML) | Known typologies: SWIFT/LoU abuse, direct DB manipulation, entitlement self-grant, log tampering, reversal theft, dormant takeover |
| **L2 — Unsupervised / UEBA** | Isolation Forest, Autoencoder, ECOD/COPOD, OCSVM (PyOD, ensemble) | Cold-start novelty / behavioural anomalies: reversal clustering, bulk exfiltration, suspense-nostro lapping, alert suppression |
| **L3 — Supervised GBDT** | LightGBM (default) / XGBoost / CatBoost + TreeSHAP, calibrated | Precision event scoring on labelled typologies: beneficiary-then-approve, fake-vendor, ghost payroll, alert suppression |
| **L4 — Sequence / time-series** | USAD, TranAD, Anomaly-Transformer, DeepLog, LAXCAT (explainable) | Low-and-slow / session behaviour: rogue trading, bulk data exfiltration |
| **L5 — Graph / relational** | GraphSAGE / GAT / hetero-GNN + XGB-on-graph-features | Collusion rings, maker-checker subgraphs, fake-vendor and ghost-payroll shared-identity links |
| **L6 — Fusion** | Transparent stacked meta-learner (logistic/shallow LightGBM) + calibration | One calibrated 0–100 risk score with reason codes over all layer outputs |
| **L7 — Dashboard** | Investigator UI (prioritized, explainable alerts) | Human EDD triage and (where warranted) human-raised block request — alert-only |

---

## L1 — Rules / Business-Rules Engine (deterministic gateway)

> Source of truth: `backend/rules_engine/` (engine + YAML rule packs), blueprint Part 20.1 / 24.5 / 18.1, `docs/detection-coverage-map.md`. L1 is the deterministic, *necessary-but-insufficient* floor that leads the stack and hard-short-circuits on known-bad events.

### 1. Purpose & what fraud it catches

L1 is the deterministic Layer-1 gateway: it encodes *known* insider-fraud typologies and the bank's Separation-of-Duties (SoD) / toxic-combination matrix as pure predicates that fire before any ML runs. It is designed to be **cold-start-safe (works day 1 with no labels), instantly explainable, and always-correct on the "we already know this is bad" cases** (blueprint Part 20.1). The engine docstring states its role plainly: *"the deterministic, necessary-but-insufficient Layer 1 … signals a hard hit for the L1 short-circuit … works at cold start (no labels). Pure: no ML, no DB, no network"* (`backend/rules_engine/engine.py:1-7`).

Named typologies it catches (from `rules.yaml` + `named_rules.py` + `privileged.py`):

- **SWIFT↔CBS reconciliation mismatch** (`SWIFT_CBS_MISMATCH`) — the PNB/LoU control: a SWIFT instrument with no reconciling CBS transaction. This is L1's *primary/sole* detector in the coverage map (`docs/detection-coverage-map.md:39`, marked **L1** bold).
- **New-beneficiary-then-high-value-approve** (`NEW_BENEFICIARY_THEN_HIGHVALUE`) — new payee created, then a high-value payment inside a short latency window.
- **Dormant reactivation → drain** (`DORMANT_REACTIVATION_DRAIN`) — long-dormant account reactivated and drained.
- **Direct DB write without an application transaction** (`DB_WRITE_WITHOUT_APP_TXN`) — privileged below-the-app manipulation; primary for "direct DB manipulation" (`docs/detection-coverage-map.md:42`, **L1 + L2**).
- **Entitlement self-grant / privilege escalation** (`ENTITLEMENT_SELF_GRANT`).
- **Off-hours activity** (`OFF_HOURS_ACTIVITY`) and **structuring just under a threshold** (`JUST_UNDER_THRESHOLD`).
- **Privileged-session correlation family** (`backend/rules_engine/privileged.py`): `PRIVILEGED_SESSION_CORRELATION`, `ORPHANED_ACCOUNT_USE`, `LEAST_PRIVILEGE_VIOLATION`, `LEAVER_WINDOW_EXFIL` (bulk-export/exfil in a leaver's notice window), `NO_LEAVE_STREAK`.
- **Maker-checker / SoD toxic combinations** (`backend/rules_engine/sod_matrix.py`): same actor as maker+checker, isolated maker-checker pair (collusion-ring candidate), self-grant, and held-entitlement conflicts.

### 2. Technique(s) chosen — the exact "model"

There is **no ML in L1 by design** — it is a deterministic rules/BRE evaluator. Each rule is a pure predicate `(ctx, cfg) -> RuleHit | None` (`named_rules.py:16`, signature documented in `rule.py:45-46`). `RulesEngine.evaluate()` (`engine.py:96-123`) iterates every enabled `RuleConfig`, invokes its bound predicate from a registry `{**NAMED_RULES, **PRIVILEGED_RULES}` (`engine.py:54`), then scores the event against the `SoDMatrix` (`sod_matrix.py:49-116`). The blueprint's verdict for this layer is **"Hybrid … it is not an ML choice — it is the cheap, explainable, always-correct floor that the ML layers build on"** (Part 20.1). Recommended implementations named in the blueprint are Drools, a Rust/Go rules-gateway, Flink-CEP, or OPA for entitlement logic (Part 20.1, tech table l.302); this repo's implementation is a pure-Python predicate engine decoupled from the API app (`rule.py:2-6`) plus a deployable **OPA/Rego** bundle (`backend/rules_engine/opa/entitlement.rego`) kept in lockstep for the least-privilege/entitlement decisions.

### 3. Dataset — what it evaluates / is exercised on

L1 is **stateless and label-free at inference**: it evaluates a single canonical L0 event `dict` plus an online-feature `dict` (`RuleContext`, `context.py:14-17`) — no training set, no DB, no network. It reads L0 event field-groups (`actor`, `action`, `object`, `context`, `linkage`) and online features materialized by DATA (e.g. `minutes_since_new_beneficiary`, `account_dormant_days`, `maker_checker_same_actor`, `held_entitlements`).

For validation and for feeding the downstream fusion, the synthetic generator in `data/sim/` produces labelled traces that map 1:1 onto these rules: `data/sim/scenarios/beneficiary_then_approve.py` injects a `create_beneficiary` at ~02:14 (off-hours) followed ~19 min later by an `approve_payment` of INR 4,800,000 by an isolated maker/checker pair — exactly the `NEW_BENEFICIARY_THEN_HIGHVALUE` + SoD firing path. Companion scenarios (`swift_without_cbs.py`, `dormant_takeover.py`, `privilege_self_grant.py`, `maker_checker_ring.py`, `bulk_exfil_resignation.py`) each correspond to a named rule. Labels are synthetic ground truth (`is_fraud=True`, `scenario_id`, `label_source="synthetic"` via `data/sim/scenarios/_common.py:79-93` / `data/sim/labels.py`) — honestly synthetic, not real fraud.

### 4. EDA / assumptions

L1's thresholds are **domain-expert priors, not fitted from data** — appropriate for a deterministic gateway, and honest about being synthetic. The blueprint's framing (Part 3.1, l.75) drives the design: deterministic thresholds are *"necessary but insufficient … insiders know the thresholds and stay under them,"* which is exactly why `JUST_UNDER_THRESHOLD` explicitly models structuring in a 5% band below the reporting/approval thresholds, and why L1 is never the whole system. Values like the INR 10,00,000 high-value line, 60-minute new-beneficiary window, and 180-day dormancy are compliance/SoD-driven constants encoded in YAML params (Section 7), set by Compliance under four-eyes change control rather than learned.

### 5. Feature engineering — the exact fields/features L1 uses

L1 consumes two surfaces via `RuleContext` (`context.py`):

- **L0 event fields (shortcuts):** `actor_id` (`actor.employee_id`), `verb` (`action.verb`, lowercased), `channel`, `maker_checker`, `amount` (`object.amount`), `is_off_hours` (`context.is_off_hours`), and `linkage` keys `swift_ref`, `cbs_txn_id`, `app_txn_id`, `db_write_id` (`context.py:41-68`).
- **Online features** read via `ctx.feat(...)`: `swift_without_cbs_match`, `minutes_since_new_beneficiary`, `beneficiary_age_days`, `account_dormant_days`, `account_recently_reactivated`, `is_self_grant`, `privileged_session`, `sensitive_data_access`, `account_orphaned`, `in_leaver_window`, `export_record_count`, `no_leave_days`, `least_privilege_violation`, `entitlement_not_required`, `violated_entitlement`; and for SoD: `maker_checker_same_actor`, `beneficiary_created_by`/`maker_actor`, `maker_checker_pair_isolated`, `maker_checker_partner`, `held_entitlements` (`named_rules.py`, `privileged.py`, `sod_matrix.py`). DATA materializes these into Feast/Redis; BACKEND reads them (per `context.py` docstring). Feature logic is shared across the online and batch paths (blueprint Part 18) to avoid train/serve skew.

### 6. Model built — the concrete classes in the repo

- `RulesEngine` (`backend/rules_engine/engine.py:50`) — orchestrator: hot-reload lifecycle (`reload`/`maybe_reload`), four-eyes CRUD (`upsert_rule`/`write_rule`), and `evaluate()` returning `EvalResult` (`engine.py:25-47`) with `hits`, `sod`, `l1_score`, `hard_hit`, `severity`, and `reason_codes`.
- `RuleConfig` / `RuleHit` (`rule.py:16-43`) — versioned config and a fired hit that becomes a `reason_code` of `source="rule"`.
- Predicate registries `NAMED_RULES` (`named_rules.py:181`) and `PRIVILEGED_RULES` (`privileged.py:83`).
- `SoDMatrix` / `SoDResult` / `SoDFlag` (`sod_matrix.py:49/39/28`) — toxic-combination scoring, with `DEFAULT_CONFLICTS` mirrored in `opa/entitlement.rego`.
- A process-wide `DEFAULT_ENGINE = RulesEngine()` (`engine.py:127`) for the online path.

### 7. Hyperparameters — the actual config (from YAML)

Thresholds live in hot-reloadable YAML `params` so tuning is a four-eyes *rule change, not a code change* (`rules.yaml:1-4`, `loader.py`). Concrete defaults from `backend/rules_engine/rules/rules.yaml`:

| Rule | Key params | Severity / hard_hit / version |
|---|---|---|
| `SWIFT_CBS_MISMATCH` | `{}` (linkage-driven) | high / **hard** / 1.0.0 |
| `NEW_BENEFICIARY_THEN_HIGHVALUE` | `high_value_inr: 1000000`, `window_minutes: 60`, `new_beneficiary_max_age_days: 1`, `payment_verbs:[approve_payment,payment,transfer]` | high / **hard** / 1.2.0 |
| `DORMANT_REACTIVATION_DRAIN` | `dormant_days: 180`, `drain_min_inr: 100000` | high / **hard** / 1.0.0 |
| `DB_WRITE_WITHOUT_APP_TXN` | `db_verbs:[db_write,direct_write,update_record,delete_record]` | high / **hard** / 1.0.0 |
| `ENTITLEMENT_SELF_GRANT` | `grant_verbs:[grant_entitlement,add_entitlement,role_assign,privilege_escalation,self_grant]` | high / **hard** / 1.0.0 |
| `OFF_HOURS_ACTIVITY` | `{}` | medium / soft / 1.1.0 |
| `JUST_UNDER_THRESHOLD` | `thresholds_inr:[1000000,5000000]`, `band: 0.05` (5% below) | medium / soft / 1.0.0 |
| `PRIVILEGED_SESSION_CORRELATION` | `sensitive_verbs:[export,bulk_export,db_write]` | high / soft / 1.0.0 |
| `LEAVER_WINDOW_EXFIL` | `exfil_verbs:[export,bulk_export,download,copy]`, `export_volume_min: 1000` | high / soft / 1.0.0 |
| `NO_LEAVE_STREAK` | `no_leave_days_threshold: 365` | low / soft / 1.0.0 |

Engine-level constants: `_HARD_SOD_THRESHOLD = 0.9` (a SoD score ≥ 0.9 is also a hard hit), `_SEVERITY_RANK = {low:1, medium:2, high:3}` (`engine.py:21-22`). Each predicate also emits a fixed confidence score into fusion, e.g. `SWIFT_CBS_MISMATCH`→0.95, `NEW_BENEFICIARY_THEN_HIGHVALUE`→0.9, `DB_WRITE_WITHOUT_APP_TXN`→0.92, `OFF_HOURS_ACTIVITY`→0.4 (`named_rules.py`). SoD conflict pairs come from `sod_matrix.yaml` (e.g. `[create_beneficiary, approve_payment]`, `[maker, checker]`, `[trade_capture, trade_settlement]`) with per-flag scores 0.80–0.95 (`sod_matrix.py:66-113`).

**Hard-hit short-circuit:** `hard = any(h.hard_hit for h in hits) or sod.score >= 0.9` (`engine.py:114`). Per the online-path diagram (blueprint Part 18.1, l.566), a hard hit means *"emit HIGH alert immediately (skip ML)."* This gives L1 a <5 ms budget and a graceful-degradation fallback ("if the model server is unavailable, fall back to L1 rules only" — Part 18.1). Rules are hot-reloadable and versioned; `maybe_reload()` re-reads on an mtime/size fingerprint change (`loader.py:34-42`) so an audited four-eyes change takes effect without a restart.

### 8. Why a deterministic rules layer leads — and why not the alternatives

The blueprint anchors this on the "rules-only vs pure-ML vs hybrid" analysis (Part 3.1, Part 20.1). **Candidates:** pure rules; pure ML; hybrid. **Verdict: hybrid, with rules first.** Rationale, grounded in the blueprint:

- **Pure rules alone fail** — they catch *yesterday's* fraud, drown analysts in false positives, and *"insiders know the thresholds and stay under them"* (Part 3.1). Hence L1 is explicitly labelled *necessary-but-insufficient* and is never the whole system.
- **Pure ML alone fails here** — it is *"unexplainable for the 'we already know this is bad' cases and can't encode hard compliance logic"* (Part 20.1). SoD/toxic-combination logic (maker=checker, self-grant, SWIFT↔CBS reconciliation) is *deterministic compliance truth*, not a probability — it must be a hard rule, not a learned score.
- **Cold start** — rules *"handle cold start (day 1, no labels)"* (Part 20.1). The ML layers (L2 unsupervised, L3 GBDT) need baselines/labels that don't exist on day 1; L1 works immediately.
- **Latency & defensibility** — deterministic evaluation is <5 ms, fully reproducible, and audit-friendly; it degrades gracefully (rules-only fallback) so the system "never goes dark."

Note the contrast with the *ML* layers' benchmark reasoning (L2's ADBench verdict: Isolation Forest / ECOD / COPOD over DeepSVDD/DAGMM, blueprint l.682-684): that "classical-beats-deep, no-free-lunch" argument governs L2–L5. L1's justification is different in kind — it is *not* an accuracy/benchmark choice at all but the deterministic compliance floor those benchmarked ML layers build on. The through-line (Part 20.4, l.774) — simple/deterministic methods win on cost, latency, and explainability — applies most strongly to L1: it is the cheapest, most explainable, most defensible layer, so it leads the stack.

### 9. Outputs — what L1 emits into fusion

`RulesEngine.evaluate()` returns an `EvalResult` (`engine.py:25-47`) exposing:

- **`l1_score`** — `max` of all fired rule scores and the SoD score (`engine.py:112-113`). This becomes the **`L1_rule` column** in the L6 fusion feature matrix (`LAYER_COLUMNS = ("L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph")`, `ml/layers/l6/stacked_meta.py:20`). In `L6Fusion.fuse_one`, an `L1_rule` score ≥ `contributing_threshold` (default 0.5) adds **`L1_rules`** to the alert's **`contributing_layers`** (`ml/layers/l6/fusion.py:24-30, 83-96`).
- **`reason_codes`** — each `RuleHit.to_reason_code()` and each `SoDFlag.to_reason_code()` emit `{"source": "rule", "code": <CODE>, "detail": <human text>}` (`rule.py:41-42`, `sod_matrix.py:35-36`). `source="rule"` is one of the valid `REASON_SOURCES` on the ML-side `ReasonCode` contract (`ml/base/interfaces.py:46-76`), so L1 hits flow verbatim into the final `Alert.reason_codes` (`interfaces.py:101-113`) assembled by L6. Provenance codes are carried verbatim (e.g. `NEW_BENEFICIARY_THEN_HIGHVALUE`, `SOD_MAKER_CHECKER_SAME_ACTOR`), giving investigators an exact, auditable "why."
- **`hard_hit` + `severity`** — a hard hit drives the online short-circuit to an immediate HIGH alert (skip ML); otherwise the L1 score/reason-codes are handed to L6 fusion for calibrated blending with the ML layers.

The system remains **alert-only** throughout — L1 scores and explains; it never auto-blocks (`docs/detection-coverage-map.md:7-9`).

---

## L2 — Unsupervised anomaly (UEBA cold-start)

### 1. Purpose & what fraud it catches
L2 is the **cold-start, no-labels** layer: it learns each entity's *normal* behaviour and flags deviations, so the system produces signal on day one before any confirmed-fraud labels exist (`ml/layers/l2/__init__.py` docstring: "L2 unsupervised UEBA detectors (ML-3; blueprint §7, §20.2)"; blueprint l.153 "L2 unsupervised carries you through cold start (no labels needed) and catches *novel* deviations"). It is the second line after L1 rules and its job is the deviations that hard rules cannot enumerate.

Per the detection-coverage map (`docs/detection-coverage-map.md`, "Layer participation summary"), L2 is named for these typologies:
- **reversal theft (branch)** — reversal clustering per operator, deposit-then-reverse
- **dormant-account takeover** — reactivation → activity, silent channel enrollment
- **suspense/nostro lapping** — item aging; same person posts & reconciles
- **rogue trading** — won't-take-leave, late/cancelled-rebooked trades
- **direct DB manipulation (privileged)** — DB write with no app txn, off-hours (L2 is a *primary* layer here alongside L1)
- **bulk data exfiltration** — download volume vs baseline, leaver-window
- **alert suppression (AML)** — one analyst clearing a disproportionate share

The common thread is *behaviour that is abnormal for this person / this peer group*, which is exactly what a per-entity UEBA baseline expresses.

### 2. Technique(s) chosen — the exact models in our code
A **PyOD-based unsupervised ensemble** wrapped by `L2Ensemble` (`ml/layers/l2/ensemble.py`). The concrete detector classes shipped in `ml/layers/l2/` are:
- `IsolationForestDetector` (`isoforest.py`) — **primary**, PyOD `IForest`, sklearn `IsolationForest` fallback.
- `EcodDetector` / `CopodDetector` (`ecod_copod.py`) — parameter-free tail-probability detectors (PyOD `ECOD`/`COPOD`, numpy empirical-CDF fallback).
- `AutoEncoderDetector` (`autoencoder.py`) — symmetric MLP autoencoder (torch), PCA-reconstruction fallback; used chiefly for **per-feature reconstruction-error explanations**.
- `OneClassSVMDetector` (`ocsvm.py`) — sklearn RBF One-Class SVM for the "smaller-scale" case (subsamples large training sets, default cap `max_train=2000`).

`L2Ensemble` fits **2–3** of these (`raise ValueError("L2Ensemble fuses 2-3 detectors")`) and fuses their normalised scores. The one-screen default ensemble (`_default_detectors()`) is **IsolationForest + ECOD + AutoEncoder**; note the *training* entry point `train_l2` (`ml/pipelines/train/l2.py`) deliberately defaults to a **torch-free IsolationForest + ECOD** pair so it can run in the same process as the LightGBM-based layers without the macOS dual-libomp segfault (see `_optional.py` note on `KMP_DUPLICATE_LIB_OK`). HBOS/CBLOF/PCA appear in the blueprint's candidate list but are *not* shipped as detector classes; the implemented set is IF / ECOD / COPOD / AutoEncoder / OCSVM.

Every detector degrades to a numpy/sklearn fallback so the module always imports even when PyOD/torch are absent (`ml/_optional.py` `HAS_PYOD`, `HAS_TORCH`).

### 3. Dataset — what it trains/scores on
L2 is unsupervised, so it trains on a window of **assumed-normal** behaviour and needs **no labels**. Input is the **per-entity feature matrix** built by `entity_level_features(events)` in `ml/adapters/featurize.py` (`index = employee_id`), aggregated from flattened L0 events. Train and serve go through the *same* featurize functions (docstring: "no train/serve skew").

The data source in this repo is the **synthetic simulator** under `data/sim/`:
- `population.py` generates up to ~50k employees with `role / department / branch / tenure_days / manager_id / peer_group / privileged_flag` across 10 bank roles (teller, ops_maker, ops_checker, dba, sysadmin, loan_officer, appraiser, trader, aml_analyst, vendor_admin).
- `normal_behaviour.py` emits benign, role-appropriate L0 events with diurnal/weekly rhythms (e.g. tellers in branch hours; DBAs on nightly batch that is off-hours-but-benign) — this is the "normal window" L2 fits on.
- `scenarios/*` inject the fraud typologies (e.g. `rogue_trader.py`, `bulk_exfil_resignation.py`, `dormant_takeover.py`, `suspense_lapping.py`, `alert_suppression.py`), which supply the *positives* used only for evaluation, not for L2 fitting.

`train_l2` fits on the normal per-entity matrix, persists **99th-percentile thresholds** from the fitted scores (`thresholds={"global_99": ...}`), and applies **exponential time decay** (`time_decay_weights`, default `halflife_days=30.0`) so recent behaviour weighs more.

### 4. EDA / assumptions (be honest: it's synthetic)
There is no classical EDA over real telemetry — the repo's data is **synthetic-only** (blueprint Part 21: "two data sources… (A) synthetic carries cold start… (B) real telemetry once wired up"; `population.py` docstring golden rule 2: "no real PII is ever produced"). The modelling assumptions baked into L2 are:
- **Normality assumption** — the training window is predominantly benign, so anomalies are rare-tail (the AutoEncoder threshold is the 99th percentile of *training* reconstruction error, i.e. training data is treated as "normal"; `autoencoder.py`).
- **Peer comparability** — entities are only meaningfully judged against *comparable* peers, which motivates the peer-relative baseline (see §5). The synthetic population is generated with an explicit `peer_group` field precisely so this holds.
- **Diurnal/role structure exists** — normal events carry role-specific hours/verbs, so features like `offhours_rate` and per-verb counts are informative.
- **Poisoning is a real threat** — the training window can be gradually corrupted by a "low-and-slow" insider; L2 explicitly guards against this rather than assuming clean data (see §6).

### 5. Feature engineering — the exact features
Two paths matter. The **model input** is the per-entity aggregate matrix from `entity_level_features(events)` (`ml/adapters/featurize.py`), keyed by `employee_id`:
- `n_events`
- `amount_mean`, `amount_std`, `amount_max`, `amount_sum`
- `offhours_rate` (mean of `context.is_off_hours`)
- `n_distinct_verbs`, `n_distinct_devices`, `n_distinct_geos`, `n_distinct_bene`
- `privileged_flag`, `leaver_flag`, `tenure_days`
- per-risk-verb counts: `n_approve_payment`, `n_create_beneficiary`, `n_export`, `n_grant_entitlement`, `n_db_write`

Before fitting, `train_l2` transforms this matrix with **`L2Ensemble.peer_relative_features`**, which z-scores each numeric feature against its **peer-group** mean/std (peer group derived from `actor.peer_group` via `peer_groups_from_events`, else a `__global__` group; falls back to global std then 1.0 for groups with <2 members). This makes L2 judge "abnormal *relative to comparable colleagues*", which the ensemble docstring frames as both a **fairness** control (§29, compare like-with-like, not against protected attributes) and an **evasion** countermeasure (§19.2, an attacker can't hide by matching the global average if they stand out within their own peer group). Inside each detector, `as_matrix` (`_common.py`) coerces to a finite float matrix (NaN/inf zero-filled), and OCSVM/AutoEncoder additionally z-standardise via `Standardizer` (SVMs and AEs are scale-sensitive).

(The richer per-event feature set — `log1p_amount`, `amount_z_personal`, `new_beneficiary`, `velocity_1h`, `swift_without_cbs`, `db_write_no_app_txn`, one-hot risk verbs — lives in `event_level_features` and feeds the supervised L3 layer, not L2.)

### 6. Model built — the concrete detector/ensemble classes
- **`IsolationForestDetector`** (`ml/layers/l2/isoforest.py`): PyOD `IForest` (sklearn `IsolationForest` fallback). Score = average path length (shorter path ⇒ more isolated ⇒ more anomalous). `score_samples` returns rank-normalised scores in [0,1] via `normalize_scores(method="rank")`.
- **`EcodDetector` / `CopodDetector`** (`ml/layers/l2/ecod_copod.py`): share `_TailDetector`. PyOD `ECOD`/`COPOD`; numpy fallback computes per-feature `-log(min(P(X≤x), P(X≥x)))` empirical-CDF tail probabilities summed across features (`_empirical_tail_neglogp`), with Laplace-smoothed floor `eps=1/(n_train+1)`. `explain` emits per-feature tail-probability contributions for the top-k worst features.
- **`AutoEncoderDetector`** (`ml/layers/l2/autoencoder.py`): torch symmetric MLP (`Linear→ReLU→Dropout→Linear(bottleneck)→ReLU→Linear→ReLU→Dropout→Linear`), MSE loss, Adam, early stopping on a held-out validation split; anomaly score = per-row reconstruction error; `is_anomaly` flags rows above the 99th-pctile training threshold. PCA-reconstruction fallback when torch is absent. Its `explain` emits per-feature reconstruction-error reason codes — this is *why* the AE is in the default ensemble.
- **`OneClassSVMDetector`** (`ml/layers/l2/ocsvm.py`): sklearn RBF OCSVM, subsampled for tractability.
- **`L2Ensemble`** (`ml/layers/l2/ensemble.py`): fits 2–3 members, fuses normalised member scores (`fuse="mean"` default, `"max"` optional), then rank-normalises the fused score. A diverse ensemble is itself an evasion countermeasure (§19.2). `explain` is delegated to the AutoEncoder member so the ensemble carries contestable per-feature reason codes (§29.2).
- **`train_l2` + `LowAndSlowPoisoningGuard`** (`ml/pipelines/train/l2.py`): the guard resists gradual training-set poisoning via **peer-anchoring** (baseline anchored to the entity's peer group, not just its own history) plus a **CUSUM change-point** test (`cusum_change_point`) over the entity's amount series; a flagged entity's post-change-point tail is excluded from the fitted baseline (`change_threshold=1.0`, `peer_drift_threshold=2.5`).

### 7. Hyperparameters — the actual config/defaults
Defaults match blueprint Part 20.2 exactly (`ml/layers/l2/__init__.py`: "Defaults match Part 20.2 EXACTLY"):
- **Isolation Forest** (`isoforest.py`): `n_estimators=150`, `max_samples=256` (Liu et al. sub-sampling default ψ=256), `max_features=1.0`, `expected_rate="auto"` (contamination; overridable), `random_state=GLOBAL_SEED`. PyOD's `contamination` (which only sets the label threshold, not `decision_function`) is mapped `"auto"→0.1` so the consumed raw scores are identical either way; `max_samples` is clamped to ≤ n_rows.
- **ECOD / COPOD** (`ecod_copod.py`): **parameter-free** (used as-is from PyOD), per blueprint l.687.
- **AutoEncoder** (`autoencoder.py`): `bottleneck_ratio=0.35` (blueprint's "¼–½ of input dim", enforced ∈(0,1)), `dropout=0.2` (enforced ∈[0.1,0.3] per §20.2), `epochs=60`, `batch_size=64`, `lr=1e-3`, `patience=8`, `val_frac=0.2`, `threshold_pct=99.0`, ReLU, MSELoss, `random_state=GLOBAL_SEED`.
- **One-Class SVM** (`ocsvm.py`): `kernel="rbf"`, `nu=0.05`, `gamma="scale"`, `max_train=2000`.
- **Ensemble** (`ensemble.py`): `fuse="mean"`, `peer_group_col="actor.peer_group"`, `version="0.1.0"`.
- **Training** (`train/l2.py`): `halflife_days=30.0` time decay, persisted `global_99` (99th-percentile) threshold, poisoning-guard `change_threshold=1.0`, `peer_drift_threshold=2.5`.
- **Seed**: `GLOBAL_SEED = 1405` (`ml/config/seeds.py`), matched to DATA's `SimConfig.seed` for cross-workstream reproducibility.
- **Score normalisation**: rank-normalisation to [0,1] (`normalize_scores(method="rank")`, `ml/base/interfaces.py`).

### 8. Why this / why NOT the alternatives (ADBench tradeoff)
The choice is grounded in **ADBench (Han et al., NeurIPS 2022; 30 algorithms × 57 datasets, 98,436 experiments)**, cited at blueprint §20.2 (l.682) and §31 (l.767):
1. **No-free-lunch is real** — no unsupervised method statistically dominates across datasets, so the design commits to a *default + short shortlist*, not "one true model" (l.666).
2. **Classical beats/ties deep** — simple detectors (Isolation Forest, ECOD, COPOD, HBOS, CBLOF, PCA) are competitive with, and frequently beat, deep unsupervised methods (**DeepSVDD, DAGMM**) while being orders of magnitude faster with far fewer knobs. Corroborated by TimeEval (a PCA baseline "surprisingly outperforms many recent deep-learning approaches").
3. **Even a little supervision beats the best unsupervised method** — which is why L2 is explicitly a *cold-start* layer that hands off to the supervised L3/L5 + EDD feedback loop, not the final word.

**Verdict (l.683):** Isolation Forest as primary default, ECOD/COPOD as parameter-free companions, autoencoder added **only** where per-feature reconstruction-error explanations (or non-linear "normal") are needed — run 2–3 in an ensemble and fuse. This is implemented literally: IF primary, ECOD/COPOD tail detectors, AE for explanations, ensemble of 2–3.

**Why over the alternatives (l.684):** Isolation Forest is linear-time, low-memory, scales to bank volumes, needs almost no tuning, and is robust on high-dimensional mixed features — exactly what cold-start production needs. ECOD/COPOD are **parameter-free**, fully reproducible, and easy to defend to audit. **DeepSVDD/DAGMM are explicitly rejected**: they cost far more to train/serve and do **not** reliably win in ADBench — "a bad trade for production" (blueprint §31 comparison table l.767: DeepSVDD/DAGMM = "cost without reliable gain"). This also fits the platform's "trees/simple methods in the hot path, deep nets out of it" latency principle (l.589) — L2 scores inline. The AutoEncoder is the one deep member retained, and only as an *explanation* generator, not as the primary scorer.

### 9. Outputs — score & reason codes into fusion
- **Score:** `L2Ensemble.score_samples` returns a per-entity anomaly score in **[0,1]** (rank-normalised fused ensemble score). This is delivered as the `L2_unsupervised` column consumed by L6 fusion (`ml/layers/l6/stacked_meta.py`: `LAYER_COLUMNS = ("L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph")`).
- **Reason codes:** `ReasonCode(source="shap", feature=<feature>, detail=..., contribution=<share>)` — from the AutoEncoder member (`"autoencoder reconstruction error"`), the tail detectors (`"empirical tail-probability outlier contribution"`), or a coarse IF code (`feature="isolation_path_length"`). These conform to the `BACKEND.md §2` reason-code shape defined in `ml/base/interfaces.py` (`REASON_SOURCES = ("rule","shap","graph","attention")`; L2's per-feature codes use `source="shap"`).
- **Into the alert:** L6 (`ml/layers/l6/fusion.py`) turns L2's [0,1] score into a **`contributing_layers`** entry labelled **`"L2_unsupervised"`** (via `_LAYER_LABEL`) whenever `layer_scores["L2_unsupervised"] >= contributing_threshold` (default `0.5`), and merges L2's reason codes through `assemble_reason_codes` into the final `Alert` (`contributing_layers`, `reason_codes`) emitted per entity. L2's own `model_version` is `l2_ensemble@0.1.0`.

**Key files:** `ml/layers/l2/{ensemble,isoforest,ecod_copod,autoencoder,ocsvm,_common,__init__}.py`; `ml/pipelines/train/l2.py`; `ml/adapters/featurize.py` (`entity_level_features`); `ml/base/interfaces.py` (`BaseDetector`, `ReasonCode`, `normalize_scores`); `ml/config/seeds.py`; `ml/layers/l6/{fusion,stacked_meta,reason_codes}.py`; blueprint §20.2 (l.680–690) & §31 table (l.767); `docs/detection-coverage-map.md`; `docs/model-card-index.md`; `data/sim/{population,normal_behaviour,scenarios}`.

---

## L3 — Supervised GBDT (Precision Event Scorer)

L3 is the supervised, label-driven precision layer of the Hawk-Eye stack. Where L2 (unsupervised UEBA) fires on novelty with no labels, L3 is the *workhorse event-level scorer* that turns accumulated labels into a calibrated per-event fraud probability. The blueprint frames it as "the precision workhorse once the feedback loop has produced labels" (blueprint l.154) and "the tabular supervised layer" (l.188). Code lives in `ml/layers/l3/` and the training/inference wiring in `ml/pipelines/train/l3.py`; label/imbalance/transfer strategies in `ml/strategies/`.

### 1. Purpose & typologies caught

L3 scores individual L0 events for `P(fraud)` and emits TreeSHAP reason codes. Per the detection-coverage map (`docs/detection-coverage-map.md` l.61 and blueprint l.61), L3 is the primary/contributing layer for:

- **Beneficiary-then-approve (toxic combo)** — new-beneficiary → high-value approval by an isolated maker/checker pair (L1 + L3 + L5; `data/sim/scenarios/beneficiary_then_approve.py`).
- **Fake-vendor / billing** — vendor address = employee, round/sequential invoices, single-client vendor (L1 + L3 + L5).
- **Alert suppression (AML watchers)** — one analyst clearing a disproportionate share, reopened-then-cleared (L2 + L3).
- **Ghost employees / payroll** — no tax footprint, duplicated bank details across payees (L1 + L3 + L5; `data/sim/scenarios/ghost_employee_payroll.py`).

These are typologies with a repeatable, learnable event-level fingerprint (amounts, verbs, off-hours, maker/checker role, new-beneficiary flag) — exactly what a tabular gradient-boosted tree excels at once labels exist.

### 2. Technique(s) — the exact models in code

Three histogram-based gradient-boosted decision tree (GBDT) scorers, all subclassing `ml.base.BaseScorer` (contract: `predict_proba(X) -> [0,1]`, `reason_codes(X)`):

- **`LightGBMScorer`** (`ml/layers/l3/lightgbm_scorer.py`) — the **default GBDT** (leaf-wise histogram growth, fastest at scale).
- **`XGBoostScorer`** (`ml/layers/l3/xgboost_scorer.py`) — the **robust** alternative (`tree_method="hist"`, stronger regularization).
- **`CatBoostScorer`** (`ml/layers/l3/catboost_scorer.py`) — the **high-cardinality / imbalance** alternative (ordered boosting, `auto_class_weights="Balanced"`).

Every heavy import (`lightgbm`/`xgboost`/`catboost`/`shap`) lives *inside* methods, so the package always imports even when a library is absent — a clean sklearn fallback kicks in (`HistGradientBoostingClassifier` for LightGBM/CatBoost, `GradientBoostingClassifier` for XGBoost), which are themselves histogram/gradient GBDTs, so `predict_proba` still returns real probabilities in `[0,1]`. `benchmark_scorers` (`ml/layers/l3/benchmark.py`) trains all three on a **time-based split**, ranks by held-out `average_precision`, and picks the best (tie-break → LightGBM, the blueprint default). All three are then available to L6 fusion.

### 3. Dataset — what it trains/scores on

L3 trains on the **event-level table** produced by the DATA synthetic red-team simulator (`data/sim/`), which injects the exact typologies above (`data/sim/scenarios/*.py`) into a synthetic population (`data/sim/population.py`) at a **realistic rare fraud rate of ~0.1–1%** (`data/sim/labels.py`, blueprint Part 21.1). Labels are kept in a **separate table keyed by `event_id`** to avoid leakage (`data/sim/labels.py`; blueprint Part 21.4) and are joined at train time via `ml.adapters.featurize.join_event_labels`, which reindexes `is_fraud` onto the feature index (missing → benign). Label sources (blueprint Part 5.4, l.815) are known cases (gold), L1 rule hits (weak), synthetic ground truth, and — the compounding engine — EDD feedback. This matches the blueprint's blunt data verdict: *there is no drop-in pre-trained model for your bank* (l.29); production signal comes from own telemetry + synthetic scenarios + the feedback loop.

### 4. EDA / assumptions (honest)

The design is grounded in the blueprint's benchmark-driven analysis rather than exploratory analysis of real bank data (none exists — insider fraud is bank-specific and labels are scarce/sensitive, l.29/l.183). The operative EDA assumptions baked into the code are:
- **Extreme class imbalance** (~0.5–1% positive) — `imbalance.py` header states this explicitly.
- **Temporal structure matters** — splits must be by time, never random (blueprint l.706); every split in L3 (`_split_valid`, `benchmark._temporal_split_xy`, `train_l3`) is time/index-ordered.
- **Synthetic caution** — public corpora (IEEE-CIS, PaySim, CERT, Elliptic) are for prototyping/benchmarking/transfer only; PaySim's balance columns leak and synthetic data is unrealistically easy (l.190). The transfer stance is "public result = sanity check, never production performance" (l.194), reflected in `transfer_learning.load_public_source` being a synthetic-fallback STUB.

### 5. Feature engineering — the exact features

L3 consumes `ml.adapters.featurize.event_level_features(events)` — a per-event numeric matrix indexed by `event_id`, built by the **same function at train and serve** to avoid train/serve skew, and leakage-safe (no label, no future). The named features:

- **Amount:** `amount`, `log1p_amount`, `amount_z_personal` (per-employee grouped z-score of amount).
- **Temporal / off-hours:** `hour`, `dow`, `is_weekend`, `is_off_hours`.
- **Actor risk flags:** `tenure_days`, `privileged_flag`, `leaver_flag`, `notice_period`.
- **Maker/checker (SoD):** `is_maker`, `is_checker`.
- **Object/linkage:** `has_beneficiary`, `has_account`, `has_swift_ref`, `swift_without_cbs`, `db_write_no_app_txn`, `new_beneficiary` (first-appearance of an employee↔beneficiary pair).
- **Velocity:** `velocity_1h` (rolling 1-hour event count per employee).
- **Verb one-hots** for the high-signal `RISK_VERBS`: `verb_approve_payment`, `verb_create_beneficiary`, `verb_export`, `verb_grant_entitlement`, `verb_db_write`, `verb_login`, `verb_post_journal`.

Columns are the dotted flattened L0 names (`actor.employee_id`, `object.amount`, `action.verb`, …); missing columns degrade gracefully to zeros so partial synthetic fixtures still yield a valid matrix.

### 6. Model built — concrete classes

- `LightGBMScorer` / `XGBoostScorer` / `CatBoostScorer` (`ml/layers/l3/{lightgbm,xgboost,catboost}_scorer.py`) — the three GBDT detectors.
- `CalibratedScorer` (`ml/layers/l3/calibration.py`) — wraps any `BaseScorer`, refits the base on the training portion and calibrates on a time-ordered held-out tail; `to_0_100(p)` maps probability to the backend 0–100 integer risk score; `reliability_summary` reports base-rate/mean-predicted/ECE.
- Imbalance helpers (`ml/layers/l3/imbalance.py`): `scale_pos_weight`, `class_weight_dict`, `sample_weight`, `negative_subsample`, `focal_loss_objective`.
- Explanations (`ml/layers/l3/treeshap.py`): `tree_shap_reason_codes` (online) and `offline_interaction_values` (offline-only).
- `benchmark_scorers` / `BenchmarkResult` (`ml/layers/l3/benchmark.py`).
- Scarce-label strategies (`ml/strategies/`): `PUClassifier` (Elkan–Noto PU), `SelfTrainingClassifier` (semi-supervised), `TransferEncoder` (pretrain/fine-tune).
- Training pipeline: `train_l3` / `L3TrainResult` (`ml/pipelines/train/l3.py`).

### 7. Hyperparameters (from code/config, clamped to blueprint bands)

The scorer constructors encode the blueprint Part 20.3 (l.703–705) params and **clamp** to the documented bands so misconfiguration cannot drift out:

**LightGBM** (`lightgbm_scorer.py`): `objective="binary"`, `metric="average_precision"` (falls back to `auc`), `num_leaves=63` (clamped `[31,255]`), `max_depth=-1`, `learning_rate=0.03` (clamped `[0.02,0.05]`), `n_estimators=1500` (clamped `[1000,3000]`) **with early stopping** (`early_stopping_rounds=50`), `feature_fraction=0.8`, `bagging_fraction=0.8`, `bagging_freq=1`, `min_child_samples=100` (clamped `[50,200]`), and `is_unbalance=True` (or `scale_pos_weight=neg/pos` when `use_scale_pos_weight=True`).

**XGBoost** (`xgboost_scorer.py`): `tree_method="hist"`, `max_depth=6` (clamped `[4,8]`), `eta=0.03` (clamped `[0.01,0.05]`), `subsample=0.8`, `colsample_bytree=0.8`, `min_child_weight≥5`, `scale_pos_weight=neg/pos`, `eval_metric="aucpr"`, `objective="binary:logistic"`, early stopping.

**CatBoost** (`catboost_scorer.py`): `depth=8` (clamped `[6,10]`), `learning_rate=0.05` (clamped `[0.03,0.1]`), `l2_leaf_reg=5` (clamped `[3,10]`), `auto_class_weights="Balanced"`, `eval_metric="PRAUC"`.

**Shared:** `valid_frac=0.2` time-ordered early-stopping tail; `random_state=1405` (= `GLOBAL_SEED`, matching DATA's `SimConfig.seed`, `ml/config/seeds.py`). **Calibration:** `CalibratedScorer(method="isotonic", valid_frac=0.25)` (isotonic default, Platt/sigmoid alternative). **Imbalance:** `negative_subsample(ratio=5.0)` inside the 1:3–1:10 band; `focal_loss_objective(gamma=2.0, alpha=0.25)`. The `train_l3` pipeline runs time-aware CV (`n_cv_splits=3`), subsample+`scale_pos_weight` fit, isotonic calibration, then reports AUPRC / Rec@K (`rec_at_k=50`).

**Class-imbalance handling (blueprint l.208/274):** the code implements the full prescribed combination — (a) `is_unbalance`/`scale_pos_weight=neg/pos` or `auto_class_weights="Balanced"`; (b) `negative_subsample` 1:3–1:10 (default 1:5, preserving time order so downstream temporal splits stay valid); (c) optional focal loss (Lin et al. 2017) to down-weight easy negatives; (d) **then** post-hoc isotonic/Platt calibration on a held-out set, because GBDT margins after class-weighting/subsampling are *not* probabilities (`calibration.py` header). Primary metrics are **AUPRC and Recall@K, never accuracy** (blueprint l.837).

**Scarce-label strategies (blueprint Part 5.4/5.5):** `PUClassifier` (Elkan–Noto 2008) treats unlabeled as negative then corrects `P(y=1|x)=P(s=1|x)/c` with `c` estimated on held-out labeled positives, and exposes `reliable_negatives` so "unknown" is never treated as "benign". `SelfTrainingClassifier` pseudo-labels high-confidence unlabeled points (`threshold=0.9`, `max_iter=3`) and retrains. `TransferEncoder` pretrains an encoder on a public corpus (CERT/Elliptic; torch autoencoder, PCA fallback) and fine-tunes a `class_weight="balanced"` logistic head — with `from_scratch_baseline` for honest comparison.

### 8. Why GBDT — why NOT the alternatives

The choice is grounded in the blueprint's independent-benchmark analysis (Part 20.3, "Candidates" l.695 onward), not single-method papers:

- **Grinsztajn et al. (NeurIPS 2022, 45 datasets):** tree models (XGBoost/GBT/RF) remain SOTA on medium-sized tabular data *even ignoring* their speed advantage; hyperparameter tuning does **not** make neural nets competitive, and the gap persists on numeric-only features (l.697). NNs are hurt by uninformative features, are rotationally invariant (bad for tabular), and struggle with irregular target functions.
- **Shwartz-Ziv & Armon (Information Fusion 2022):** XGBoost outperforms deep tabular models; deep-alone does not win (l.698).
- **Fraud-specific head-to-heads (l.699):** CatBoost led (F1 0.9161) > XGBoost (0.8926) > LightGBM (0.8812) on a 1.85M credit-card set; a real-time study found LightGBM best on speed/large-data medians, CatBoost most stable under imbalance/high-cardinality, XGBoost robust but slightly less stable. All three GBDTs beat DNNs at lower compute.

**Verdict (l.700, l.768):** LightGBM as the production **default** (histogram/leaf-wise growth = fastest at scale), CatBoost as the strong alternative when high-cardinality categoricals dominate (beneficiary IDs, merchant/branch/GL codes), XGBoost as the robust baseline — benchmark all three per metric+latency (which `benchmark_scorers` does).

**Why NOT deep tabular nets (TabNet / FT-Transformer):** the evidence says they won't beat tuned GBDTs here and cost far more (l.700/l.768). GBDTs train in minutes, serve in microseconds (ideal for the ~5–30ms hot path, l.584/l.589), handle missing values and mixed types natively, and pair with **exact, fast TreeSHAP** — decisive given the regulatory explainability requirement.

**Explainability tradeoff (blueprint Part 20.6/18):** the live path uses **plain TreeSHAP only** (`tree_shap_reason_codes`, exact for trees, ~5–20ms) — chosen over KernelSHAP/LIME (sampling noise, manipulable) because TreeSHAP is exact and game-theoretically grounded. **SHAP interaction values are OFFLINE-ONLY** (`offline_interaction_values`, O(features²) per row) and explicitly banned from the hot path (l.585). When `shap` is absent, a crude `feature_importance × standardized-value` fallback keeps the reason-code contract.

### 9. Outputs into fusion

Each L3 scorer emits **(a)** a calibrated `predict_proba` in `[0,1]` (mapped to the 0–100 backend risk integer via `to_0_100`), and **(b)** per-row TreeSHAP reason codes: `list[ReasonCode(source="shap", feature=<name>, contribution=<signed SHAP value>)]`, top-k by `|contribution|`, most-influential first (`ml/base/interfaces.py` — `source="shap"` is a valid `REASON_SOURCES` member).

Into L6 fusion (`ml/layers/l6/fusion.py`, `stacked_meta.py`), L3's score enters the stacked meta-learner as the **`L3_gbdt`** column (`LAYER_COLUMNS = ("L1_rule","L2_unsupervised","L3_gbdt","L4_sequence","L5_graph")`). If the L3 score clears `contributing_threshold` (default 0.5), the alert lists **`L3_gbdt`** in `contributing_layers`, and its `shap`-sourced `ReasonCode`s are merged by `assemble_reason_codes` into the BACKEND.md §2 alert (source priority `rule > graph > attention > shap`, so deterministic rule provenance leads and SHAP features substantiate). The result is a single calibrated, explainable Alert per entity — L3 supplying the precision score and the feature-level "why".

---

## L4 — Sequence (the "WARNING" layer)

*Sources grounded in: `ml/layers/l4/*` (`windows.py`, `baselines.py`, `usad.py`, `tranad.py`, `anomaly_transformer.py`, `deeplog.py`, `laxcat.py`, `gate.py`), `ml/pipelines/train/l4.py`, `ml/pipelines/inference/async_l4_l5.py`, `ml/eval/metrics.py`, `data/sim/scenarios/{rogue_trader,bulk_exfil_resignation}.py`, `docs/detection-coverage-map.md`, `docs/model-card-index.md`, and Blueprint §20.4 / §22.2 / §18 / §14.*

### 1. Purpose & what fraud it catches

L4 models the **ordered event stream of an actor over time** rather than a single tabular row. Its job is to catch fraud whose signal lives in the **shape and order of a sequence of actions**, not in any one event: session-level misbehaviour and **"low-and-slow" behavioural drift** where each individual event looks benign but the trajectory is anomalous. The module docstring (`ml/layers/l4/__init__.py`) calls L4 the **WARNING layer (ML-5)**.

Per `docs/detection-coverage-map.md` (§ "Layer participation summary") and `docs/model-card-index.md`, L4 is named for two typologies:

- **Rogue trading** — mismarking, late/cancelled-then-rebooked trades, no-leave-taken streaks. The synthetic scenario `data/sim/scenarios/rogue_trader.py` emits exactly this *sequence*: a `no_leave_streak` event, then an off-hours `book_trade` → `cancel_trade` → `rebook_trade` chain (INR 12M → cancelled → 9.5M rebook), then a `mark_position` (11.8M) diverging from an `independent_valuation` (8.9M). The fraud is the *pattern of steps*, not any single verb.
- **Bulk data exfiltration** (leaver window) — `data/sim/scenarios/bulk_exfil_resignation.py` injects six large off-hours `export` events to a personal channel (`channel="dlp"`, `table="customer_pii"`) spread across the notice period, with the actor carrying `leaver_flag`/`notice_period`. The signal is a **spike/run within the ordered stream**.

Because tabular layers (L2 unsupervised, L3 GBDT) score events largely independently, a determined insider can keep every single event under per-event thresholds while the *cumulative sequence* drifts. L4 windows the stream so that drift becomes visible. The docs are honest that this is **mitigation, not elimination** (`detection-coverage-map.md` §"What this map does not claim": *"A determined low-and-slow insider can still drift a baseline; mitigated, not eliminated"*).

### 2. Technique(s) chosen — exactly what is in the code

L4 is deliberately a **suite with a gate**, not a single model. The non-negotiable contract (docstring `ml/layers/l4/__init__.py`, `gate.py`, Blueprint §20.4/§22.2) is: **run simple baselines FIRST, keep a deep model ONLY if it beats them under honest, non-point-adjust evaluation.**

- **Simple baselines (run first)** — `ml/layers/l4/baselines.py`:
  - `WindowedPCADetector` — PCA over flattened windows; anomaly = reconstruction error.
  - `WindowedIsolationForestDetector` — IsolationForest over flattened windows.
  - `MatrixProfileDetector` — matrix-profile-style nearest-neighbour distance (each window's distance to its closest *other* window; discords = anomalies), z-normalised, no external deps.
  - `ConvAutoencoderBaseline` — tiny 1-D conv autoencoder under torch, with a **PCA-reconstruction fallback** when torch is absent.
- **Deep candidates (torch, gated)** — kept only if they earn it:
  - `USAD` (`usad.py`) — two adversarially-trained autoencoders on a shared encoder (Audibert et al. 2020).
  - `TranAD` (`tranad.py`) — transformer encoder with **focus-score self-conditioning + adversarial reconstruction** (Tuli et al. 2022).
  - `AnomalyTransformer` (`anomaly_transformer.py`) — compact attention+reconstruction with an **association-discrepancy** proxy (Xu et al. 2022).
  - `DeepLog` (`deeplog.py`) — next-event **LSTM language model over the verb sequence per session**, with a pure-numpy n-gram fallback (Du et al. 2017).
- **Explainer** — `LAXCAT` (`laxcat.py`): a supervised CNN + **variable-attention + temporal-attention** classifier (Hsieh et al. 2020/2021). It is *not* a cold-start detector; it needs labels and exists to explain flagged sessions ("which variables, which time intervals").
- **Gate** — `keep_if_beats_baselines` (`gate.py`): compares the deep model's VUS-PR (or range-aware AP) against the *best* baseline and returns `keep=True` only if `margin > min_margin`. It hard-asserts `POINT_ADJUST_ENABLED is False`.

The **LAXCAT-style attention** described in the task is realised in two places: `LAXCAT` itself (explicit variable + temporal attention heads) and the `AnomalyTransformer` (multi-head self-attention over the window with association-discrepancy scoring).

### 3. Dataset — what it trains/scores on

L4 consumes the **L0 event log**, not a pre-aggregated feature table. Input is a pandas DataFrame of ordered events keyed on `actor.employee_id`, `ts`, `action.verb`, `context.session_id`, `object.amount`, `context.is_off_hours` (the column constants in `windows.py`). Data is **synthetic**, produced by the simulator in `data/sim/`:

- **Normal behaviour** — `data/sim/normal_behaviour.py` stamps `Context.is_off_hours` (via `data.config.is_off_hours`) and mints a **session id per employee per day** (`session_id=make_id("session", emp.employee_id, ts.date().isoformat())`). This defines what a "session" is in the data.
- **Fraud traces** — the two L4 typology injectors above (`rogue_trader`, `bulk_exfil_resignation`), which carry a fraud label per event via `fraud_label(...)`.

Labels are **weak/window-level**: `build_windows` in `windows.py` sets a window's label to the **max over its events** (1 if the window contains any fraud event), and `build_verb_sequences` labels a session 1 if any of its events is fraud. The baselines are **unsupervised** (`BaseDetector.score_samples → [0,1]`); labels are used only for the honest evaluation/gate and for the supervised `LAXCAT`.

### 4. EDA & assumptions

Because the data is synthetic, "EDA" here is really the **design rationale in the blueprint**, and the code is honest about it. The governing observations (Blueprint §20.4, §14):

- The deep-MTS-anomaly literature is *"plagued by the point-adjust evaluation protocol,"* under which even near-random scores look SOTA; **simple baselines frequently match or beat deep models** once PA is removed (Wu & Keogh; Kim et al. AAAI'22; TimeEval — *"a PCA baseline surprisingly outperforms many recent deep approaches"*). This is why `ml/eval/metrics.py` sets `POINT_ADJUST_ENABLED = False` **by construction** (there is deliberately no PA function to select) and the gate asserts it stays off.
- Class imbalance is extreme (fraud is rare within any actor's stream), so evaluation uses **VUS-PR / range-aware precision-recall**, never ROC-AUC alone, and always includes the simple baselines in the table, **split by time** (`train_l4` evaluates baselines with `average_precision`/`vus_pr`; comment "Eval is split by time; point-adjust is never used").
- The core behavioural assumption (Blueprint §6.2): baselines drift, so peer-anchoring + long windows + change-point thinking are needed to resist **low-and-slow baseline poisoning** — L4 windows are the temporal half of that antidote.

### 5. Feature engineering — the exact L4 features

L4's feature space is intentionally **compact and leakage-safe**, built by `step_features(df)` in `windows.py` (one row per event, index-aligned):

- `log_amount` — `np.log1p(clip(object.amount, 0, None))`.
- `off_hours` — the boolean `context.is_off_hours` cast to int.
- A **one-hot over the eight high-signal verbs** in `SEQ_VERBS`: `login`, `approve_payment`, `create_beneficiary`, `export`, `grant_entitlement`, `db_select`, `db_write`, `post_journal` → columns `verb=login`, `verb=export`, etc.

So each event is a **10-dimensional vector** (`log_amount`, `off_hours`, 8 verb one-hots). Two window representations are built:

- **Dense numeric windows** — `build_windows(events, labels, window=20, stride=1, min_events=1)` → a `WindowSet` with `X` shaped `(n_windows, window, n_features)`, plus `entity`, `end_ts`, `y`, `feature_names`. Windows are **per-entity sliding windows** over the time-ordered stream (`_entity_order` sorts by `__entity__, __ts__` with a stable mergesort). Entities with fewer than `window` events are **right-padded by repeating the last event** so short synthetic actors still yield one window. `WindowSet.flat` reshapes to `(n_windows, window*n_features)` for the PCA/IF baselines. This is the input for PCA, IF, matrix-profile, conv-AE, USAD, TranAD, and AnomalyTransformer.
- **Integer verb sequences** — `build_verb_sequences(events, by="session")` → per-session `list[list[int]]` (verb→id vocab, id 0 = `<pad>`/unknown), keyed on `context.session_id` when present else `actor.employee_id`. This is the DeepLog input (next-event language model). A "session" is thus the **per-employee/per-day event group** minted by the simulator.

### 6. Model built — concrete detector classes (with files)

| Model | Class / file | Mechanism |
|---|---|---|
| Windowed PCA | `WindowedPCADetector` (`baselines.py`) | `sklearn.decomposition.PCA` on flattened windows; score = mean squared recon error, per-feature error exposed via `explain`. |
| Windowed IsolationForest | `WindowedIsolationForestDetector` (`baselines.py`) | `sklearn.ensemble.IsolationForest` on flattened windows; `-decision_function` → min-max normalised. |
| Matrix profile | `MatrixProfileDetector` (`baselines.py`) | z-normalised nearest-neighbour distance to the training set, self-match excluded on the diagonal. |
| Conv autoencoder | `ConvAutoencoderBaseline` (`baselines.py`) | 1-D `Conv1d` enc/dec under torch; PCA fallback without torch. |
| USAD | `USAD` (`usad.py`) | shared MLP encoder + two decoders; AE2 reconstructs AE1's output (`w3`); score = `alpha*‖x−w1‖ + (1−alpha)*‖x−w3‖`. |
| TranAD | `TranAD` (`tranad.py`) | 1-layer `TransformerEncoder`; phase-1 recon error becomes a **focus score** scaling phase-2 input; two decoders trained adversarially. |
| Anomaly Transformer | `AnomalyTransformer` (`anomaly_transformer.py`) | `nn.MultiheadAttention` (2 heads) reconstructs the window; score blends recon error with **attention-map entropy** (low entropy = concentrated = anomalous). |
| DeepLog | `DeepLog` (`deeplog.py`) | `nn.Embedding → nn.LSTM → nn.Linear` next-verb LM; score = mean surprisal of actual next verbs; numpy n-gram fallback. |
| LAXCAT (explainer) | `LAXCAT` (`laxcat.py`) | grouped `Conv1d` per variable → **temporal-interval attention** (softmax over `n_intervals`) → **variable attention** (softmax over channels) → linear classifier. |

All detectors return `[0,1]` scores (`BaseDetector.score_samples`) via `normalize_scores(..., method="minmax")`; `LAXCAT` is a `BaseScorer` returning `predict_proba`. Heavy torch imports live **inside** the methods so every module imports even without torch (deep `fit` then raises a clear `require('torch')`; DeepLog falls back to n-gram).

### 7. Hyperparameters (actual defaults in code)

- **Windowing**: `window=20`, `stride=1`, `min_events=1` (`build_windows`); the default 20-step window sits inside the Blueprint §20.4 recommendation of ~10–100 steps. `SEQ_VERBS` = 8 verbs → 10 features/step.
- **WindowedPCADetector**: `n_components=8`, `window=20`; `PCA(random_state=1405)`, k clamped to `min(n_components, n_features, n_samples−1)`.
- **WindowedIsolationForestDetector**: `n_estimators=150`, `max_samples=min(256, n)`, `max_features=1.0`, `contamination="auto"`, `random_state=1405`.
- **ConvAutoencoderBaseline**: `latent_dim=8`, `window=20`, `epochs=8`, Adam `lr=1e-2`, MSE.
- **USAD**: `latent_dim=8`, `epochs=12`, `alpha=0.5`; two Adam optimisers `lr=1e-2`; the `(1/n)` vs `(1−1/n)` epoch schedule per the USAD paper.
- **TranAD**: `d_model=16`, `nhead=2`, `dim_feedforward=2*d_model`, `num_layers=1`, `dropout=0.0`, `epochs=10`, Adam `lr=1e-2`.
- **AnomalyTransformer**: `d_model=16`, `num_heads=2`, `epochs=10`, Adam `lr=1e-2`; final score = `0.5*recon + 0.5*discrepancy`.
- **DeepLog**: `hidden=16`, `window=5` (context length), `epochs=12`, Adam `lr=1e-2`, `CrossEntropyLoss`; left-padded contexts; Laplace-smoothed n-gram fallback.
- **LAXCAT**: `n_intervals=4`, `conv_channels=8`, `window=20`, `epochs=25`, Adam `lr=5e-3`, `BCEWithLogitsLoss` with **`pos_weight = neg/pos`** for class imbalance (Blueprint §5.5).
- **Gate** (`keep_if_beats_baselines`): `metric="vus_pr"`, `min_margin=0.0`, `max_buffer=5`.
- **Reproducibility**: every torch model seeds `torch.manual_seed(1405)`; sklearn uses `random_state=1405`.

### 8. Why this — and why NOT the alternatives

The design is a direct application of the Blueprint's benchmark-anchored reasoning (§14, §20.4), which distrusts single-method papers and anchors on independent benchmarks (**ADBench, TimeEval, Grinsztajn, GADBench**):

- **Why baselines-first + a gate.** TimeEval (71 algos × 967 datasets) shows a **PCA baseline outperforms many deep approaches**; Wu & Keogh show trivial one-liners hit "SOTA" on flawed benchmarks; Kim et al. show **point-adjust lets a random baseline beat SOTA**. So L4 leads with windowed PCA / IF / matrix-profile / small AE, evaluates with **VUS-PR and range/affiliation-aware PR, never PA**, and admits a deep model only through `keep_if_beats_baselines`. Deep MTS models "**must earn their place**" (`__init__.py` docstring, Blueprint §20.4 verdict).
- **Why TranAD/USAD over the newest transformer.** The Blueprint keeps TranAD as the best deep candidate **for engineering reasons, not benchmark hype** — it was designed for *scarce labels, high volatility, ultra-low inference time* (focus-score self-conditioning + adversarial training, fast at inference); USAD (adversarial AEs) is a fast, stable second. That is why the async lane runs them **off the hot path** (§18): they *upgrade* an alert, never block. Picking a heavy transformer by default would be "buying complexity and cost for unproven gain."
- **Why not point-adjust / why the honest eval.** `Fancy Algorithms and Flawed Evaluation Methodology` (arXiv 2308.13068) shows Anomaly Transformer under PA is essentially emitting anomalies at near-regular intervals and still scores well. The repo encodes this critique structurally: `POINT_ADJUST_ENABLED = False` with **no PA function to select**, and the gate `assert`s it.
- **Why LAXCAT is an explainer, not a detector.** LAXCAT is supervised (needs labels), so per Blueprint §20.1/§20.4 it is a Layer-4 *enhancement* for explaining flagged sessions ("which variables, which time intervals"), not a cold-start detector — reflected in it subclassing `BaseScorer` (predict_proba) while the cold-start detectors subclass `BaseDetector`.
- **Why sequence modelling at all (vs the tabular layers).** L2/L3 score events largely independently and can miss a **slow drift** that keeps every event under threshold. Windowing the actor's ordered stream (`build_windows`, `build_verb_sequences`) exposes runs, order, and reconstruction/surprisal anomalies that a per-event model cannot see — the rogue-trader `book→cancel→rebook` chain and the exfil `export` spike are *sequence* signals. This is why the coverage map assigns rogue trading and bulk exfiltration to L4.

### 9. Outputs — score + reason codes into fusion

L4 emits per-window/per-session anomaly scores in `[0,1]` plus **attention-sourced reason codes**, consumed by fusion **asynchronously** (`ml/pipelines/inference/async_l4_l5.py`, Blueprint §18):

- **Score**: `score_samples`/`predict_proba` → `[0,1]`.
- **Reason codes** (`ReasonCode`, contract in `ml/base/interfaces.py`; `source` must be one of `rule|shap|graph|attention`): L4 uses **`source="attention"`**.
  - `LAXCAT.reason_codes` emits, per row, the **dominant time interval** (e.g. `steps[10:15] (interval 3/4)` as `detail`) and the **top variables by variable-attention** (`feature=<var>`, `contribution=v_w·t_w`).
  - `WindowedPCADetector.explain` emits the top features by per-feature window reconstruction error (`detail="window reconstruction error"`).
  - `DeepLog.explain` emits `code="DEEPLOG_NEXT_EVENT"`, the last verb, and `detail="low predicted probability of next verb"`.
- **Fusion handoff** (`AsyncUpgrader.upgrade`): L4 runs **off the hot path** and can only **UPGRADE** an existing fast-lane alert — never lower it, never block (`blocked` is always `False`). It:
  - maps the `[0,1]` score to `risk_score = round(score*100)` and takes `max(old, new)` (upgrade-only);
  - appends **`"L4_sequence"`** to `contributing_layers` (label map `{"L4": "L4_sequence"}`) when it raises the score;
  - extends the alert's `reason_codes` with the attention reason codes;
  - recomputes `severity` via `severity_from_score` (≥70 high, ≥40 medium) and keeps `status` open.

Net: L4 is the sequence-aware **second opinion** that turns "each event looked fine" into "this actor's *trajectory* is anomalous," and it says so with variable+temporal attention evidence — while structurally refusing to inflate its own credibility (no point-adjust) or its own latency (async, upgrade-only, never blocks).

---

## L5 — Graph / Relational (collusion rings, mule networks, maker-checker collusion)

### 1. Purpose & typologies caught

L5 is the **relational** layer: it scores the *primary entity — the employee* — using not just that employee's own behaviour but the **network of shared entities around them** (accounts, beneficiaries, devices, vendors) and the **other employees they are linked to**. It exists because a whole class of insider fraud is *invisible to any per-event or per-entity model that treats records independently*. The blueprint is blunt about this: graph neural networks (and the graph-feature approach) are "the right and almost only tool for **collusion rings, mule networks, maker-checker collusion, and toxic-combination-in-practice**" (blueprint l.26, §Layer 5 l.282–285).

Concretely, from `docs/detection-coverage-map.md` (l.63) L5's typologies are:

- **Collusion rings / embedded accomplices (primary)** — the recurring, isolated maker/checker pair or small cluster. This is the hardest category ("engineered collusion rings", blueprint l.284, l.418) and L5 is the *only* layer listed as primary for it.
- **Beneficiary-then-approve (toxic combination)** — the maker-checker pairing frequency signal (L1 + L3 + **L5**).
- **Fake-vendor / billing** — vendor↔employee shared-attribute links (`vendor` node type; L1 + L3 + **L5**).
- **Ghost employees / payroll** — duplicated bank details / shared identity links (L1 + L3 + **L5**).

The canonical scenario this layer is built against is materialised in the data generator: `data/sim/scenarios/maker_checker_ring.py` injects "a recurring, isolated colluding maker/checker pair (or small cluster) sharing a `ring_id` (RNG-*)" — the same `ops_maker` initiates and the same `ops_checker` approves four ₹1,200,000 payments on consecutive days, producing an isolated subgraph. That structural isolation-plus-recurrence is exactly what tabular L3 cannot see (each approval looks locally normal) and what a graph model *can*.

### 2. Technique(s) chosen — what is actually in the code

`ml/layers/l5/__init__.py` sets `DEFAULT_SCORER = XGBGraphScorer`. The layer ships a graduated model zoo, matching the blueprint's "start cheap, add deep surgically" verdict (l.735):

- **DEFAULT: XGB-Graph / RF-Graph** — `ml/layers/l5/xgb_graph.py`. Per-node features are concatenated with their **k-hop neighbourhood aggregates** and fed to a gradient-boosted tree ensemble. This is the GADBench winner and the blueprint DEFAULT for L5.
- **Inductive GNN: GraphSAGE** — `ml/layers/l5/graphsage.py`. A 2-layer `SAGEConv` (mean aggregator) → linear head, for scoring *new* nodes not seen at train time.
- **Camouflage/heterophily-resistant specialist GNNs** — `ml/layers/l5/specialized_gnns.py`: `GATScorer` (attention), `HGTScorer` (heterogeneous-transformer flavour via `TransformerConv`), `BWGNNScorer` (Beta-Wavelet band-pass), `CAREGNNScorer` (learned similarity gate), `PCGNNScorer` (label-balanced pick-and-choose), registered in `SPECIALIZED_GNNS`.

All of these consume the same substrate: the **typed heterogeneous entity graph** built by `ml/layers/l5/graph_build.py` (`EntityGraph`).

### 3. Dataset it trains/scores on

L5 trains and scores on the **synthetic simulator output**, honestly synthetic (the blueprint earmarks the real Elliptic Bitcoin graph only as a *prototype* dataset, l.191; production data is the simulated bank event stream).

- **Node/edge substrate:** `EntityGraph.ingest()` (`graph_build.py`) is fed *flattened L0 events* — the dotted-schema records emitted by `data/sim/simulator.py` — and derives nodes and typed edges directly from event columns.
- **Node features (X):** the **per-employee entity feature table** from `ml/adapters/featurize.py::entity_level_features` (index = `employee_id`). `_align_node_features` (`xgb_graph.py`) attaches these 1:1 to employee nodes; non-employee nodes get zero feature rows so signal can still flow through them during aggregation.
- **Labels (y):** `featurize.entity_labels` — an employee is labelled 1 if they are ever a fraud actor (`actor_id`) on a fraud label. Fraud labels come from `data/sim/labels.py` / `scenarios/_common.py::fraud_label`, which stamp the `ring_id` on maker-checker-ring events.
- **Training pipeline:** `ml/pipelines/train/l5.py::train_l5` builds the graph, does an **entity-disjoint split** (no employee in both train and test — l.60), fits `XGBGraphScorer` on the training entities over the *full* graph, and evaluates on held-out entities.

### 4. EDA / assumptions

Being explicit: the "EDA" here is over **synthetic data**, so it is really *assumption validation of the generator*, not discovery on real logs. The design assumptions (blueprint §20.5, §6.5) drive it:

- Fraud graphs exhibit **heterophily / camouflage** — "fraudsters deliberately connect to benign nodes and mimic their features — exactly your doc's 'engineered to look normal'" (l.733). This is why plain GCN/GIN "often do no better than an MLP" and why the layer needs camouflage-resistant options.
- The collusion signal is **structural, not point-wise**: recurring maker↔checker pairing, isolated subgraphs, shared-identity/shared-device links (§6.5 l.248–252).
- **Extreme imbalance** → the headline metric is **AUPRC / average precision + Rec@K**, never accuracy or ROC-AUC (blueprint l.665; `train_l5` reports `auprc` and `recall_at_20`).
- The load-bearing empirical assumption — the **"aggregation lift"** — is *tested*, not assumed: `ml/layers/l5/gadbench_ablation.py` trains at 0, 1, 2 hops and asserts AUPRC improves. The test `tests/ml/test_l5.py::test_gadbench_0_to_2_hop_ablation_lift` builds a homophily ring and asserts `auprc_2 >= auprc_0` and, more strongly, a clear lift (`auprc_2 > auprc_0 + 0.1`). Evaluation is deliberately **time-aware / entity-disjoint, never random, never point-adjusted** (`gadbench_ablation.py` docstring).

### 5. Feature engineering — the exact features this layer uses

Two feature families are concatenated into the design matrix (`xgb_graph.py::graph_design_matrix`).

**(a) Node features** — per-employee, from `entity_level_features` (`ml/adapters/featurize.py`): `n_events`, `amount_mean`, `amount_std`, `amount_max`, `amount_sum`, `offhours_rate`, `n_distinct_verbs`, `n_distinct_devices`, `n_distinct_geos`, `n_distinct_bene`, `privileged_flag`, `leaver_flag`, `tenure_days`, and verb counts `n_approve_payment`, `n_create_beneficiary`, `n_export`, `n_grant_entitlement`, `n_db_write`.

**(b) k-hop graph aggregates** — computed by `graph_build.py::k_hop_aggregates` for k ∈ {1,2} (blueprint recipe l.738: "mean/sum/max of neighbor features, degree, centrality, shared-attribute counts"). Exactly:

- **Structural columns (always):** `graph_degree`, `graph_centrality` (eigenvector centrality via `networkx.eigenvector_centrality_numpy`, or a pure-numpy power-iteration fallback), and `graph_shared_attr_count` (per-node count of incident shared-attribute edges — the direct **collusion proxy**, `EntityGraph.shared_attribute_counts`).
- **Per-hop neighbour aggregates** for each node feature `c` and hop `h ∈ {1,2}`: `nbr_mean_{c}_h{h}`, `nbr_sum_{c}_h{h}`, `nbr_max_{c}_h{h}`, plus `nbr_count_h{h}`. The 2-hop reachability is computed *strictly 2-hop-only* (self and direct neighbours excluded) so hop-2 captures the "new ring" beyond immediate contacts.

The test asserts these exact columns exist: `{"graph_degree", "graph_centrality", "graph_shared_attr_count"} <= set(...)` (`test_l5.py` l.188).

### 6. Model built — the concrete detector classes

- **`XGBGraphScorer(_BaseGraphScorer)`** — `ml/layers/l5/xgb_graph.py`, the DEFAULT. `_build_design` → build/refresh graph → `graph_design_matrix(X, graph, k=2)` → GBDT. Booster preference **LightGBM → XGBoost → sklearn `HistGradientBoostingClassifier`** (always-available fallback), selected in `_make_model`.
- **`RFGraphScorer(_BaseGraphScorer)`** — RandomForest variant, no booster dependency.
- **`GraphSAGEScorer(BaseScorer)`** — `graphsage.py`: inductive `_SAGE` module, two `SAGEConv(..., aggr="mean")` layers + `Linear(hidden, 2)` head, edge_index built from the dense adjacency (self-loops added when no edges exist); features standardized per-column; scores mapped back to the employee rows of `X`.
- **Specialist GNNs** — `specialized_gnns.py`, sharing `_BaseSpecializedGNN` plumbing: `_GAT` (two `GATConv`, 2 heads then 1), `_HGT` (`TransformerConv`), `_BW` (`SGConv` low-pass ⊕ linear high-pass — heterophily-resistant band-pass), `_CARE` (SAGEConv + sigmoid similarity gate), `_PC` (SAGEConv + residual).
- **Explainer** — `gnn_explainer.py::explain_node`: model-agnostic **edge-perturbation** attribution (remove each incident edge, measure the score/feature-vector drop) — PyG's `GNNExplainer` is used when a torch model is wired (`pyg_gnn_explainer_available`).

All subclass `ml/base/interfaces.py` contracts: `predict_proba → P(fraud) ∈ [0,1]` (clipped), `reason_codes → list[list[ReasonCode]]`; `layer = "L5"`.

### 7. Hyperparameters (actual config in code)

**XGBGraphScorer LightGBM path** (`xgb_graph.py::_make_model`): `objective="binary"`, `n_estimators=300`, `num_leaves=31`, `learning_rate=0.05`, `feature_fraction=0.8`, `bagging_fraction=0.8`, `bagging_freq=1`, `min_child_samples=10`, `scale_pos_weight=spw` where `spw = max(1.0, n_neg/n_pos)` (imbalance recipe), `random_state=1405`, `n_jobs=1`.
**XGBoost path:** `tree_method="hist"`, `n_estimators=300`, `max_depth=6`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `min_child_weight=5`, `eval_metric="aucpr"`, `scale_pos_weight=spw`.
**sklearn HistGB fallback:** `max_iter=300`, `learning_rate=0.05`, `max_depth=6`, `l2_regularization=1.0`, `class_weight="balanced"`.
**RFGraphScorer:** `n_estimators=300`, `min_samples_leaf=2`, `class_weight="balanced_subsample"`.
**Aggregation depth:** `k=2` (default in `XGBGraphScorer.__init__` and `train_l5`).

**GraphSAGEScorer** (`graphsage.py`) — the blueprint reference config named in the docstring: 2-layer GraphSAGE, mean aggregator, `hidden=128`, `epochs=30`, `lr=0.01`, `dropout=0.5`, Adam with `weight_decay=5e-4`, `CrossEntropyLoss` with class weight `[1.0, n_neg/n_pos]` for imbalance. **Specialist GNNs** default `hidden=64`, same epochs/lr/dropout.

### 8. Why this / why NOT the alternatives (the design tradeoff)

The verdict comes straight from **GADBench** (Tang et al., NeurIPS 2023; ~29 models × 10 datasets up to ~6M nodes), blueprint l.731–736 and the summary table l.770:

- **Why XGB-Graph / RF-Graph is the default:** GADBench's counterintuitive headline is that *tree ensembles with simple neighbourhood aggregation outperform the best specialized GNNs* — XGB-Graph beat the best GNN (BWGNN) by **+2.0% AUROC, +12.9% AUPRC, +9.8% Rec@K** (fully-supervised), and were **more efficient** and **scaled better** to large graphs. It also **reuses the L3 GBDT infrastructure** and the `scale_pos_weight` imbalance recipe — the "smart-enterprise" default that captures most of the relational signal at a fraction of the cost (l.736). This is why `DEFAULT_SCORER = XGBGraphScorer` and why the ablation asserts the 0→2-hop lift.
- **Why NOT vanilla GCN/GIN:** they "often do no better than an MLP that ignores graph structure" because fraud graphs are **heterophilous/camouflaged** (l.733) — the exact "engineered to look normal" problem. The code deliberately omits plain GCN/GIN as scorers.
- **Why GraphSAGE is still included:** it's "the standout exception" among standard GNNs (**+10.4% AUPRC** when tuned) and — decisively — it is **inductive**, so it scores streaming *new* nodes/edges (`graphsage.py` docstring: "scores employees it has never seen"). Operationally essential for the async/hourly cadence.
- **Why the specialist GNNs (CARE-GNN / PC-GNN / BWGNN / GAT / HGT) exist but aren't default:** camouflage *is* the collusion problem, so these purpose-built, camouflage-resistant architectures are brought in "specifically for the hard collusion/heterophily cases where XGB-Graph plateaus" (l.735). They require tuning, so they earn their place only when they beat the default. HGT (heterogeneous) is reserved for "richly multi-typed" graphs "only if the simpler approaches are exhausted."

The `gadbench_ablation.py` harness operationalises the whole argument: it is the acceptance test that the graph structure actually helps (`AUPRC_2hop >= AUPRC_0hop`) before the layer is trusted.

### 9. Outputs into fusion

L5 emits, per employee: a **P(fraud) score in [0,1]** and a list of **`ReasonCode`s** (`ml/base/interfaces.py`). Reason-code sourcing:

- **`XGBGraphScorer.reason_codes`** ranks the design vector by `global_importance × standardized_feature_value`; any feature named `nbr_*` or `graph_*` is emitted with **`source="graph"`** (detail "k-hop graph aggregate …"), node-local features with `source="shap"`. `REASON_SOURCES` allows exactly `{"rule","shap","graph","attention"}`.
- **GNN scorers** emit `source="graph"` (or `source="attention"` for `gat`/`hgt`) with codes like `gnn_neighbourhood` / `{kind}_neighbourhood`, detail "aggregated N typed neighbours of \<emp\>".
- **`explain_node`** emits per-edge `ReasonCode(source="graph", code="edge_{type}", detail="edge '{t}' to {ntype} {neighbour} influences {node}'s fraud score …")` — regulator-facing, the "graph evidence for collusion" the blueprint requires (l.285, l.389).

Into **fusion (L6)**: the score enters the stacked meta-learner as the **`L5_graph`** column (`ml/layers/l6/stacked_meta.py::LAYER_COLUMNS = ("L1_rule","L2_unsupervised","L3_gbdt","L4_sequence","L5_graph")`). In `L6Fusion.fuse_one`/`fuse_batch` (`ml/layers/l6/fusion.py`), L5 is added to the alert's **`contributing_layers`** as `"L5_graph"` when its score ≥ `contributing_threshold` (default 0.5), and its graph reason codes are merged into the alert's `reason_codes`. Because L5 runs **off the hot path**, it flows through the async lane (`ml/pipelines/inference/async_l4_l5.py`): `AsyncUpgrader` with `layer="L5"` **upgrades** (via `max`, never lowers, never blocks) an existing alert and appends `"L5_graph"` to its contributing layers — matching the blueprint's "trees in the hot path, deep nets out of it; L5 runs on a short async/hourly cadence and *upgrades* an existing alert" (blueprint l.589, l.598, l.577).

---

## L6 — Fusion (stacked meta-learner → calibrated 0–100 risk + reason codes)

### 1. Purpose & what it catches

L6 is not a detector of a new typology — it is the **decision layer** that blends every upstream signal (L1 rules, L2 unsupervised/UEBA, L3 GBDT, L4 sequence, L5 graph) into **one calibrated 0–100 risk score, a severity × confidence pair, and a ranked reason-code list, emitted as a single `Alert` per entity**. Its job is to (a) reconcile disagreeing base learners, (b) map raw model outputs to a *real fraud probability* so the alert threshold can be set against analyst capacity, and (c) suppress alert fatigue — the blueprint calls this out as "the #1 operational killer of fraud systems" and prescribes "one scored, explained alert per entity/event instead of one per model" (`Insider_..._Blueprint (2).md` lines 156, 487; `docs/detection-coverage-map.md` line 20: "`L6` = risk fusion (one calibrated 0–100 score)").

The typologies it *surfaces* are therefore the union of the layers': SoD / toxic-combination violations (L1), behavioural anomalies (L2), known-fraud patterns (L3), session/sequence attacks (L4) and collusion rings / self-dealing (L5). L6's distinctive contribution is catching the **weak-signal-in-isolation, strong-in-aggregate** case — an event no single layer would alert on, but whose stacked combination clears threshold (and the "rescued by graph fusion" upgrade path, §9).

### 2. Technique(s) chosen

Two artifacts implement the same design, one per side of the ML/BACKEND seam:

- **Offline / ML artifact** — `ml/layers/l6/fusion.py::L6Fusion`, composed of a **transparent stacked meta-learner** (`stacked_meta.py::StackedMetaLearner`) plus an **isotonic calibrator** (`calibration.py::RiskCalibrator`) plus a **reason-code assembler** (`reason_codes.py`). This is Wolpert-style *stacked generalization*: the base layers are level-0 learners, the meta-model is level-1 over their scores.
- **Online / BACKEND service** — `backend/fusion/service.py::FusionService`, the real-time hot-path fusion (blueprint Part 18.1). It currently ships the meta-model as an explicit stub (`L6_META_VERSION = "l6_meta@stub-2026.06.30"`; `# STUB: ML L6 meta-model + calibrator`), with the seam designed so "swapping in ML's fitted meta-model changes only `_meta_prob`" (`service.py` docstring). The stub uses a fixed logistic form `_meta_prob(...) = sigmoid(-2.2 + 1.7·L1 + 1.2·L2 + 2.4·L3 + 1.2·SoD (+ 1.0·L4))` — same functional class (logistic-over-layer-scores) as the fitted ML model, so the drop-in is coefficient-only.

### 3. Dataset

L6 does **not** train on raw features — it trains on the **per-layer score matrix** plus rule flags. Input columns are canonical and fixed: `LAYER_COLUMNS = ("L1_rule", "L2_unsupervised", "L3_gbdt", "L4_sequence", "L5_graph")` (`stacked_meta.py` line 20). `assemble_layer_matrix()` builds the meta-input frame from a dict of per-layer score vectors, **filling any missing layer with 0.0** so the meta-model always sees all five columns (a layer that didn't run — e.g. L4 before the session window matures, or L5 on the async cadence — contributes zero rather than breaking inference).

Training (`ml/pipelines/train/l6.py::train_l6`) fits over `(layer_scores: DataFrame, y)` where `y` are integer fraud labels; the base scores come from scoring the synthetic population (`data/sim`) through L1–L5, and labels come from the agent-based simulator's injected-scenario ground truth. Per blueprint discipline it is calibrated and evaluated on **AUPRC** (`metrics = {"auprc": average_precision(yv, cal), ...}`), never accuracy, and splits are time-aware upstream.

### 4. EDA & assumptions

The honest position (as with the whole stack): labels are **synthetic**, produced by the agent-based simulator, because true insider-fraud labels are scarce and the blueprint explicitly warns that "naive tabular GANs FAIL to preserve behavioural patterns" so behavioural realism must come from the simulator, not generative augmentation (blueprint lines 207–208, 811). The design assumption L6 leans on is stated in Part 20.7: the base learners "have different strengths (which yours do, by construction: rules/unsupervised/supervised/sequence/graph)", which is precisely the condition under which stacking beats naive averaging. The other operational EDA assumption is **class imbalance** — handled by `class_weight="balanced"` on both meta-model variants — and the need for **calibration** because uncalibrated fused scores make "threshold-setting guesswork" (blueprint line 757).

### 5. Feature engineering (the meta-model's inputs)

The meta-model's five "features" are the upstream **scores themselves**: `L1_rule`, `L2_unsupervised`, `L3_gbdt`, `L4_sequence`, `L5_graph`. On the online side, `FusionService.fuse()` additionally engineers a **segregation-of-duties flag** as a synthetic input, `sod = 1.0 if (features["maker_checker_same_actor"] or features["maker_checker_pair_isolated"]) else 0.0` (`service.py` lines 56–63), which enters the logistic form with weight `1.2`. The reason-code path (`backend/fusion/treeshap.py`) also reads the underlying feature vector — `new_beneficiary_to_payment_latency_min`, `maker_checker_pair_frequency_30d`, `off_hours_activity_flag`, `amount_zscore`, `privileged_session_flag` — but those drive *explanations*, not the fused probability.

### 6. Model built

- `ml/layers/l6/stacked_meta.py::StackedMetaLearner(BaseScorer)` — level-1 estimator, `layer = "L6"`. Default `kind="logistic"` → `sklearn.linear_model.LogisticRegression`; optional `kind="lightgbm"` → shallow `LGBMClassifier`. Exposes `layer_contributions()` (logistic `coef × value`, or tree importance × value) and `reason_codes()` for the transparent per-layer attribution.
- `ml/layers/l6/calibration.py::RiskCalibrator` — `sklearn.isotonic.IsotonicRegression` (default) or sigmoid/Platt; `to_risk_0_100()` maps to the integer band. `severity_confidence()` derives severity + confidence.
- `ml/layers/l6/reason_codes.py` — `assemble_reason_codes()` + `build_alert()`.
- `ml/layers/l6/fusion.py::L6Fusion` — orchestrator with `fuse_one()` / `fuse_batch()`.
- Online: `backend/fusion/service.py::FusionService` (with `calibration.py`, `reason_codes.py`, `treeshap.py`).

### 7. Hyperparameters (actual, from code)

- **Meta-model default** (`StackedMetaLearner._build`, `stacked_meta.py`): `LogisticRegression(max_iter=1000, class_weight="balanced")`. LightGBM variant: `n_estimators=120, num_leaves=7, max_depth=3, learning_rate=0.05, class_weight="balanced", verbose=-1` — deliberately shallow to stay transparent/auditable.
- **Calibration** (`RiskCalibrator`, `calibration.py`): `method="isotonic"`, `IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)`.
- **L6Fusion** (`fusion.py`): `meta_kind="logistic"`, `calibration="isotonic"`, `contributing_threshold=0.5` (the cutoff at which a layer is listed in `contributing_layers`).
- **Reason-code assembly**: `assemble_reason_codes(max_codes=6)`; source priority `{"rule":0, "graph":1, "attention":2, "shap":3}`; per-layer `reason_codes(top_k=3)`; online SHAP `shap_k=4`.
- **Thresholds / bands**: severity `HIGH ≥ 70`, `MEDIUM ≥ 40`, else `LOW` (`interfaces.py::severity_from_score`; mirrored in `backend/fusion/calibration.py` `HIGH_THRESHOLD=70`, `MEDIUM_THRESHOLD=40`). Alert **emit threshold** = `70` (`online.py::EMIT_THRESHOLD`; below it the event is recorded to ClickHouse, not surfaced). SLA `sla_days=30`.
- **Online stub coefficients** (`service.py::_meta_prob`): intercept `-2.2`, weights L1 `1.7`, L2 `1.2`, L3 `2.4`, SoD `1.2`, L4 `1.0`; a hard rule hit forces `prob = max(prob, 0.85)` ("a hard rule hit is HIGH by construction", Part 18.1).
- **Model version**: `fusion-2026.2.0` is the governed version under model-card review (`docs/model-card-index.md` lines 11, 51), online tag `l6_meta@stub-2026.06.30`.

### 8. Why this / why not the alternatives

Straight from the blueprint's Part 20.7 and the algorithm-choice matrix (line 772):

| Layer | Use this (default) | Alternative | Avoid |
|---|---|---|---|
| **L6 Fusion** | **Stacked meta-learner + isotonic calibration** | Weighted average (simplest) | Uncalibrated raw scores |

- **Stacking over naive weighted-average / rank fusion**: "stacking consistently beats naive averaging when base learners have different strengths (which yours do, by construction)" (blueprint line 758; Wolpert 1992). A fixed weighted average can't learn, e.g., that L3=0.6 co-occurring with an L1 SoD flag is far more damning than either alone.
- **Transparent meta-model (logistic / shallow LightGBM) over a deep or high-capacity blender**: "Prefer an interpretable fusion (logistic/GBM on layer outputs) so the final decision is itself explainable to audit" (blueprint line 288). This is a hard regulatory constraint — model-card-index keys an independent validation + sign-off gate to `fusion-2026.2.0` that *blocks promotion* without it; a black-box fusion would defeat that. Hence `layer_contributions()` exposes exact `coef × value` per layer.
- **Isotonic calibration over raw scores**: "Uncalibrated raw scores" are explicitly in the *Avoid* column. Calibration is what makes the 0–100 score operationally meaningful so the emit threshold (`70`) can be tuned to analyst capacity rather than guessed (blueprint lines 757, 447). Isotonic is chosen (monotone, non-parametric) with sigmoid/Platt as the fallback.
- This mirrors the stack-wide through-line (blueprint line 774): "tree-based and simple methods win or tie on accuracy while crushing deep models on cost, latency, and explainability" — L6 is the simplest, most auditable model in the stack by design, and it sits in the ~5–10 ms fusion budget (Part 18.1, line 586).

### 9. Outputs (into fusion → explanation panel)

L6 emits the BACKEND.md §2 `Alert` (`ml/base/interfaces.py::Alert`, `backend/services/api/app/schemas/alerts.py`):

- **`risk_score`** — `int(round(calibrated_prob × 100))`, 0–100.
- **`severity`** — from the 70/40 bands; a hard rule hit forces `high` (`severity_for(..., hard_hit)`).
- **`confidence`** — two consistent definitions: ML side (`severity_confidence`) uses distance from the 0.5 boundary, `min(1.0, |p − 0.5|·2)`, so scores near 0/1 are high-confidence; BACKEND side (`confidence_from`) uses **cross-layer agreement** — `0.5·agreement + 0.5·prob`, where `agreement = 1 − min(1, std(layer_scores)·2)` (tight spread ⇒ high confidence), capped at 0.99.
- **`contributing_layers`** — labels for every layer whose score `≥ contributing_threshold` (0.5), mapped via `_LAYER_LABEL` to `L1_rules / L2_unsupervised / L3_gbdt / L4_sequence / L5_graph`; falls back to `["L6_fusion"]` if none clear the bar. Online, a layer is listed when its score is present / `graph_evidence` exists (`service.py` lines 74–84).
- **`reason_codes`** — assembled from up to four provenances, **ranked rules-first then by |contribution|** (`_SOURCE_PRIORITY = rule<graph<attention<shap`, `max_codes=6`): (1) `source="rule"` verbatim L1 hits + SoD; (2) `source="graph"` L5 evidence; (3) `source="attention"`/`sequence` L4 steps; (4) `source="shap"` TreeSHAP top-k features (`shap_k=4`, plain TreeSHAP only — no interaction values inline, "those are ~quadratic in features and belong offline", blueprint line 585). The ML meta-model also injects its own `L6_meta` transparent attribution (`self.meta.reason_codes(row, top_k=3)`). This list *is* the explanation-panel payload (gauge → composition → SHAP → memo).

**"Rescued by graph fusion":** the async L5 path is the "may raise/upgrade alert" arrow in Part 18.1 (blueprint line 577) and the `ScoreComposition` "rescued by graph fusion" component in `docs/DESIGN_UPGRADE_STUDY.md` (line 42, "`<InsightCallout>` counterfactual when one source is decisive"). Concretely: `online.py::_graph_evidence()` runs an async L5 proxy that detects an isolated maker-checker pair or same-actor maker=checker, mints a deterministic `ring_id` (`RNG-10..99`), and injects `graph_evidence` into fusion. When present it (a) adds `L5_graph` to `contributing_layers`, (b) contributes graph reason codes ranked just below rules, and (c) via the meta-model's `L5_graph` coefficient can lift an otherwise sub-threshold event over the emit line — i.e. an event that L1–L4 alone left below 70 is *rescued* into an alert by the graph signal, and the reason-code list makes that graph contribution the decisive, human-readable callout.

**Contract note:** the wire severity enum is exactly `{low, medium, high}` — intentionally no `critical` band; intensity above `high` is carried by `risk_score` + `confidence`, not a fourth label (`interfaces.py` line 90–98). `pii_tokenized=True` on every emitted alert.

**Key files:** `ml/layers/l6/{fusion,stacked_meta,calibration,reason_codes}.py`, `ml/pipelines/train/l6.py`, `ml/base/interfaces.py`; `backend/fusion/{service,calibration,reason_codes,treeshap}.py`, `backend/services/api/app/pipeline/online.py`, `backend/services/api/app/schemas/alerts.py`; rationale in `Insider_Fraud_Detection_Implementation_Blueprint (2).md` (Parts 18.1, 20.7, lines 287–288, 755–758, 772) and `docs/{detection-coverage-map,model-card-index}.md`, `docs/DESIGN_UPGRADE_STUDY.md`.

---

_Generated from the live repository (ml/, backend/rules_engine/, backend/fusion/, data/sim/) + the implementation blueprint. Each layer section cites the real modules, config, and design rationale. Kept in step with the code — update alongside detector changes._