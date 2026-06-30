# Real-Time Insider & Privileged-User Fraud Detection
## A Production Implementation Blueprint for a Public-Sector Bank (On-Prem)

> **What this is.** A complete, build-it engineering and ML blueprint for the system described in your brief: *"flags anomalous or potentially fraudulent activities in real time… leverages ML to establish behavioural baselines for each user and detect deviations… provides risk scores… generates alerts with contextual explanations… and offers a dashboard for the fraud investigation team."* It is grounded in the fraud taxonomy of your reference document (ACFE Fraud Tree, RBI Master Directions, the PNB/Union Bank/ABG cases) and in current research (CERT insider-threat benchmark, USAD/TranAD/Anomaly-Transformer, LAXCAT, graph-neural-network fraud detection, the Kafka/Flink/ClickHouse production stack).
>
> **Confirmed scope.** Real production system • on-prem / India-localized • **alert-only → human enhanced-due-diligence (EDD) → then block** (never auto-blocks money) • primary target = **real-time insider/privileged behaviour**, with a secondary "slow lane" for credit/entity fraud • full telemetry available (transactions + identity/access + data-layer + change/HR) • real data plus synthetic generation.

---

## 0. Executive summary (the verdict in one page)

**The honest framing first.** No single model "stops all fraud," and any vendor or document that promises it is selling something. Your own reference doc says it plainly: fraud is most often caught by *tips*, not systems; the median scheme runs ~12 months; and the largest losses come from trusted veterans who control the very reconciliations that would expose them. What a well-built system **does** do is **collapse time-to-detection from months to minutes for the digitally-observable schemes, raise the cost and risk of every fraud attempt, and give investigators a unified, explainable, prioritized view that no human could assemble manually across siloed systems.** That is a transformational improvement — and it is achievable. "Stopping everything" is the wrong success metric; "catching far more, far earlier, with far less analyst effort, defensibly" is the right one.

**What to build:** a **multi-layer detection funnel** — not one model — that mirrors defence-in-depth:

```
Telemetry → [L0 Unified Event Model] → [L1 Rules/BRE] → [L2 UEBA baselines + unsupervised anomaly]
          → [L3 Supervised gradient boosting] → [L4 Sequence/time-series] → [L5 Graph/collusion]
          → [L6 Risk fusion + reason codes] → [L7 Investigator dashboard + EDD feedback loop] ↺ (relabels L3/L4)
```

**The technique verdict (answering your direct question):** *both* families you named are correct — for *different layers*.
- **XGBoost / LightGBM** is the **workhorse event-level scorer** (Layer 3). Tabular gradient boosting dominates fraud detection in practice and competition; it is fast, handles mixed features, and pairs natively with SHAP explanations. Use it as soon as you have labels.
- **Multivariate time-series anomaly detection (USAD, TranAD, Anomaly-Transformer)** is the right tool for **session-level and "low-and-slow" behaviour** (Layer 4) where you have sequences and few/no labels — but treat the benchmark hype with skepticism (see §7 and §14) and earn it only after the simpler layers prove out.
- **LAXCAT** is an *explainable supervised* time-series classifier (CNN + variable-attention + temporal-attention). It is excellent for **explaining a flagged session** ("which variables, which time intervals drove this") — but it needs labels, so it is a Layer-4 *enhancement*, not a cold-start detector.
- **Graph neural networks** (GraphSAGE / GAT / heterogeneous GNN) are the right and almost only tool for **collusion rings, mule networks, maker-checker collusion, and toxic-combination-in-practice** (Layer 5).
- **Unsupervised anomaly** (Isolation Forest, autoencoders, ECOD/COPOD) is what carries you through **cold start** (Layer 2), before labels exist.

**The data verdict:** there is **no drop-in pre-trained model for your bank** and there never will be — insider fraud is bank-specific and labels are scarce and sensitive. Public datasets (CERT, IEEE-CIS, PaySim, Elliptic) are for **prototyping, benchmarking, and transfer**, not production. Your production signal comes from **your own telemetry + a synthetic red-team scenario library (modelling the exact typologies in your doc) + the EDD feedback loop that turns every investigated alert into a fresh label.**

**The tech-stack verdict (on-prem, all self-hostable):** **Kafka** (ingest) → **Flink** (stateful streaming) → **Feast + Redis** (feature store) → **Python** ML training (XGBoost/LightGBM/PyTorch/PyOD/PyG) → **ONNX Runtime / Triton** serving → **ClickHouse** (the investigation/analytics store — the same engine Exabeam and IBM QRadar use for security analytics) → **React/TypeScript dashboard**. **Rust** has a precise, valuable role (the latency-critical ingest/enrichment and rules/scoring gateways); it is *not* where the ML lives.

**Build vs buy:** you almost certainly already run a SIEM and an RBI-mandated EWS/AML system. **Do not rip them out.** The differentiator — and the thing no commercial product gives you — is a **unified, entity-centric brain that fuses privileged-technical activity with business-transaction activity into one risk score**, purpose-built around *your* segregation-of-duties and toxic-combination matrix, running in *your* data centre. That is what you build; everything else you integrate.

---

## 1. The problem, reframed as an ML/engineering problem

Your reference document is a *fraud-examination* artifact. To build, we translate it into a *detection* problem with three irreducible properties:

1. **The actor is authorized.** There is no "bad login" to catch. The signal is in **intent and pattern**, not permission. This forces a **behavioural-baseline + deviation** approach (UEBA), not access control.
2. **Two overlapping populations, historically watched by two different tool stacks.**
   - *Internal/business users* (tellers, ops makers/checkers, loan officers, traders, AML analysts) → watched, if at all, by **fraud/AML transaction monitoring**.
   - *Privileged/technical users* (DBAs, sysadmins, IAM/PAM admins, devs with prod access, SWIFT operators) → watched, if at all, by **UEBA/SIEM**.
   - **The decisive cases live in the seam between them** (PNB: SWIFT not reconciled to CBS; the privileged admin who grants the entitlement the business fraudster uses). **Unifying these two views into one entity timeline is the core technical bet of this system.**
3. **Real-time is only half the problem.** The brief says "real time," and the *access/transaction* schemes (off-hours bulk download, privilege escalation, new-beneficiary→high-value payment, dormant takeover) genuinely are real-time-detectable. But the *credit/entity* schemes in your doc (ghost loans, inflated appraisals, ABG-style diversion) surface on **forensic audit years later** and **cannot** be caught "in real time." We therefore split the system into:
   - **Fast lane (primary, this build):** streaming, sub-second-to-minutes, per-event and per-session scoring of insider/privileged behaviour.
   - **Slow lane (secondary, phased):** batch, entity-and-relationship scoring for credit/vendor/collusion fraud (days-to-weeks horizon) — feeds the RBI Early-Warning-Signal (EWS) framework.

**Operating principle (your instinct, confirmed):** the model **never auto-blocks a payment**. In a bank, a false positive that halts a legitimate large transfer is itself a serious incident. The system **scores and explains → an investigator runs EDD → a human decides to block**. Every EDD disposition (true fraud / false positive / inconclusive) returns as a **label**, which is the engine of continuous improvement. This is exactly how Featurespace, Feedzai, and mature UEBA deployments operate, and it is the only defensible design under RBI's natural-justice requirements.

---

## 2. Stakeholders and what each needs from the system

A solution that "solves the problem of all stakeholders" must serve each of these explicitly. This table drives requirements.

| Stakeholder | Their core problem today | What the system must give them |
|---|---|---|
| **Fraud / Vigilance investigation team (1st users)** | Drowning in noise; no unified view; manual correlation across CBS, logs, HR | Ranked, deduplicated, **explained** alerts; entity-360 timeline; graph view; case management; low false-positive burden |
| **2nd line — Risk & Compliance** | Must run RBI EWS/RFA; tune thresholds; report to CRILC/FMR | Configurable rules/thresholds; EWS indicator coverage; CRILC/FMR-ready exports; audit of every decision |
| **3rd line — Internal Audit** | Needs independent assurance that 1st/2nd lines work | Immutable, tamper-evident audit trail; reproducibility; model-governance evidence |
| **IT / InfoSec (and PAM owners)** | Privileged activity below the app layer is invisible; standing admin rights | Privileged-session correlation; DB-write-without-app-txn detection; entitlement-change monitoring; least-privilege integration |
| **Business lines (branch, ops, treasury, credit)** | Cannot have legitimate work blocked or slowed | **Alert-only** design; zero inline blocking; minimal friction; peer-fair scoring |
| **CISO / CRO / Board (SCBMF)** | Need defensible risk posture and early warning | Risk dashboards; coverage map; trend reporting; board-level KRIs |
| **RBI / Regulator** | EWS integrated with CBS; FMR/CFR reporting; natural justice; data localization | EWS framework support; on-prem India residency; explainability; due-process workflow |
| **Data / ML Engineering** | Drift, scarce labels, maintainability | Feature store; retraining pipeline; drift monitors; model registry |
| **The employee / accused (often forgotten)** | Risk of unfair flagging; surveillance; reputational harm | Proportionality; explanation; human-in-the-loop; natural-justice workflow before any classification |

---

## 3. Why existing approaches fall short (and the build-vs-buy decision)

### 3.1 Rules-only monitoring
Deterministic thresholds are **necessary but insufficient**. They catch *yesterday's* known fraud, drown analysts in false positives, and — critically — **insiders know the thresholds and stay under them**. Your doc says this directly. Rules are Layer 1, never the whole system.

### 3.2 Commercial fraud/AML platforms (Feedzai, Featurespace ARIC, NICE Actimize, FICO Falcon, Hawk:AI)
Genuinely strong at **customer/transaction** fraud — real-time scoring, adaptive behavioural baselines, explainable reason codes, case management. **Where they fall short for *this* problem:**
- **Customer-centric, not insider-centric.** They model *customer* "normal," not *employee/privileged-user* "normal," and they don't ingest DB-audit, PAM-session, or entitlement-change telemetry.
- Many lean **supervised** and adapt slowly to **first-time/novel insider** schemes; some are **batch-oriented**.
- **Heavy and expensive** — 3–6 month implementations, professional-services-intensive, Tier-1 budgets.
- **Consortium-dependent strengths** (cross-bank pattern sharing) don't help with *internal* fraud.

### 3.3 Commercial UEBA/SIEM (Securonix, Exabeam, Microsoft Sentinel)
Built for **insider/IT threat** — per-user/entity baselines, off-hours/anomaly detection, SOAR. **Where they fall short:**
- **Generic IT-security anomalies, not banking-fraud-aware.** They flag "unusual file access," not "new beneficiary created then high-value payment approved by the same maker-checker pair," because they don't model CBS/SWIFT transaction semantics or SoD/toxic-combination logic.
- **Siloed from the AML/transaction stack** — the seam problem persists.
- Integration and tuning overhead is significant.

### 3.4 The gap — and the verdict
**No commercial product gives you a unified, entity-centric view that fuses privileged-technical activity with business-transaction activity, scored against *your* segregation-of-duties matrix, on-prem.** That is precisely the "joined-up front-to-back view nobody owns" that your doc (Part 5) identifies as the thing that separates institutions that catch rogue activity from those that don't.

**Decision:** **augment, don't replace.**
- **Keep** your SIEM (as a log source and alert sink) and your RBI EWS/AML system (coexist; feed CRILC).
- **Build** the unifying insider-fraud brain (Layers 0–7) and the investigator dashboard.
- This is *smart enterprise engineering* (your phrase) — you don't go "all in" rebuilding everything; you build the one differentiated layer and integrate the rest.

---

## 4. The solution architecture (multi-layer detection funnel)

The funnel is deliberately ordered cheap→expensive and explainable→complex. Most events are dismissed by Layer 1–2; only survivors reach the costly layers. This is how you get enterprise scale without "all-in" cost.

```
                          ┌─────────────────────────────────────────────────────────────┐
   SOURCES                │                     L0  UNIFIED EVENT MODEL                    │
 CBS / SWIFT / RTGS ─────▶│  Kafka topics → schema-normalized "actor-action-object" events │
 IAM / AD / PAM     ─────▶│  one canonical record joining who/what/where/when/onwhat        │
 DB audit / DLP     ─────▶│  enriched with HR context (role, tenure, leaver), peer group    │
 Entitlement / HR   ─────▶└───────────────┬─────────────────────────────────────────────────┘
                                          │  (Flink stateful enrichment + Feast/Redis features)
                                          ▼
        ┌───────────────────────────────────────────────────────────────────────────────────┐
        │ L1  RULES / BRE  — deterministic, explainable, instant                              │
        │   • SoD / toxic-combination matrix   • known typologies   • hard red flags          │
        │   • e.g. SWIFT↔CBS mismatch, new-beneficiary→high-value, dormant-reactivation→drain,│
        │         DB write with no app txn, off-hours privileged export, entitlement self-grant│
        └───────────────┬───────────────────────────────────────────────────────────────────┘
                        │ (most events stop here as "clear"; survivors + ALL events sampled onward)
                        ▼
        ┌───────────────────────────────┐   ┌───────────────────────────────┐
        │ L2 UEBA baselines + unsupervised│   │ L3 Supervised gradient boosting│
        │  Isolation Forest / Autoencoder │   │  XGBoost / LightGBM            │
        │  per-user & per-peer baselines  │   │  (once labels exist)          │
        │  deviation scoring (cold-start) │   │  SHAP reason codes            │
        └───────────────┬─────────────────┘   └───────────────┬───────────────┘
                        ▼                                       ▼
        ┌───────────────────────────────┐   ┌───────────────────────────────┐
        │ L4 Sequence / time-series      │   │ L5 Graph / relational          │
        │  USAD / TranAD (unsup. session)│   │  GraphSAGE / GAT / hetero-GNN  │
        │  LAXCAT (explainable, labeled) │   │  collusion rings, mule chains, │
        │  low-and-slow drift detection  │   │  maker-checker collusion       │
        └───────────────┬─────────────────┘   └───────────────┬───────────────┘
                        └──────────────┬────────────────────────┘
                                       ▼
        ┌───────────────────────────────────────────────────────────────────────────────────┐
        │ L6  RISK FUSION  — calibrated meta-score (0–100) + reason codes + contributing layers│
        │     weighted ensemble / stacked model; isotonic calibration; severity × confidence   │
        └───────────────┬───────────────────────────────────────────────────────────────────┘
                        ▼
        ┌───────────────────────────────────────────────────────────────────────────────────┐
        │ L7  ALERTING + INVESTIGATOR DASHBOARD + EDD                                          │
        │   ranked queue → entity-360 → explanation panel → graph → action → disposition       │
        │   disposition (fraud / FP / inconclusive) ──────────────────────────┐                │
        └─────────────────────────────────────────────────────────────────────┼───────────────┘
                                                                               ▼
                                                        FEEDBACK LOOP → labeled store → retrain L3/L4/L5
   CROSS-CUTTING (all layers): explainability • drift monitoring • immutable audit • model governance
```

**Why this order works for an enterprise:**
- **L1 rules** are ~free and catch the known with full explainability — they handle the "we already know this is bad" cases and satisfy compliance.
- **L2 unsupervised** carries you through cold start (no labels needed) and catches *novel* deviations.
- **L3 boosting** is the precision workhorse once the feedback loop has produced labels.
- **L4 sequence** and **L5 graph** are *added later*, only when the cheaper layers are saturated and the data justifies them — this is the "work smartly, don't go all-in" discipline.
- **L6 fusion** prevents alert fatigue by emitting *one* scored, explained alert per entity/event instead of one per model.

---

## 5. Data strategy

### 5.1 The unified event model (the foundation everything rests on)
Normalize every source into a canonical **actor → action → object** event. This single schema is what makes the privileged+business fusion possible.

| Field group | Examples |
|---|---|
| **Actor** | employee_id, role, department, branch, tenure_days, manager_id, **leaver_flag/notice_period**, peer_group_id, privileged_flag |
| **Action** | verb (login, create_beneficiary, approve_payment, db_select, export, grant_entitlement, reverse_txn, modify_account), channel, maker/checker role |
| **Object** | account_id, beneficiary_id, table/dataset, entitlement_id, instrument (SWIFT/LC/LoU), amount, currency |
| **Context** | timestamp, source_ip, device, geo, session_id, app vs DB-layer, is_off_hours, host |
| **Linkage** | correlation keys to join SWIFT↔CBS, app-txn↔DB-write, maker↔checker, employee↔customer-account |

This lands in **Kafka** (hot path) and **ClickHouse** (history/investigation).

### 5.2 What datasets you actually need (your own telemetry)
From the four confirmed buckets, the concrete feeds:
- **Transactions:** CBS posting logs, payment/SWIFT/RTGS/NEFT/IMPS/UPI message logs, GL/suspense/nostro entries, trade/treasury blotter.
- **Identity & access:** IAM/AD authentication logs, PAM privileged-session logs (CyberArk/BeyondTrust), VPN.
- **Data layer:** database audit logs (who-read/wrote-what at the DB/OS layer), DLP/egress logs, bulk-download/export records.
- **Change & HR:** entitlement/role-change logs, account-modification logs, HR joiner-mover-leaver feed (the single highest-value context signal for insider risk).

### 5.3 Public & "pre-trained" datasets — the honest answer
**Is there a dataset already trained you can drop in? No.** There is no comprehensive *real-world* public insider-banking dataset (it's too sensitive), and a model trained on someone else's distribution won't transfer to your bank's behaviour. What the public corpora are good for:

| Dataset | What it is | Use it for |
|---|---|---|
| **CMU-SEI CERT Insider Threat** (r4.2 / r5.2 / r6.2) | *The* canonical synthetic insider benchmark: 1,000–4,000 employees, ~18 months, multi-modal logs (logon, device/USB, file, email, HTTP, LDAP), with injected scenarios (after-hours+USB+exfil, job-hunting+theft, disgruntled sysadmin keylogger). Extremely imbalanced. | Prototype the **UEBA/insider layers (L2/L4)**; validate feature engineering and imbalance handling **before** your real data is wired up |
| **IEEE-CIS Fraud (Vesta, 2019)** | Real-world card-not-present, ~590k txns, ~300+ features, 3.5% fraud. Kaggle winners used **gradient boosting + heavy feature engineering** (AUC ≈ 0.91). | Prototype the **tabular supervised layer (L3)**; learn feature-engineering patterns |
| **Credit Card Fraud (ULB/European, 2013)** | 284,807 txns, 492 frauds (**0.172%**), PCA features. | The **extreme-imbalance** test bed; tune PR-AUC and resampling |
| **PaySim** (mobile-money simulator) | 6.3M synthetic transfers/cash-outs with injected fraud. **Caveat:** balance columns leak; synthetic ⇒ unrealistically easy. | **Scale/throughput** testing of the streaming pipeline; *not* a model-quality benchmark |
| **Elliptic (Bitcoin)** | 200k+ node transaction graph, labeled illicit/licit. | Prototype the **graph layer (L5)** |
| **SPEDIA (2025), Fraud Dataset Benchmark (Amazon, 9 sets)** | Newer insider / aggregated fraud benchmarks. | Broader benchmarking and ablations |

**Transfer-learning stance:** you may *pre-train* sequence/graph encoders on CERT/Elliptic and *fine-tune* on your data — but treat the public-data result as a sanity check, never as production performance.

### 5.4 The label problem (the real ML challenge) and how to beat it
Insider fraud is rare and labels are scarce — the central difficulty. Four complementary label sources:
1. **Known historical cases** — your Vigilance/CBI/forensic-audit outcomes become positive labels (few but gold).
2. **Rule hits as weak/heuristic labels** — Layer-1 confirmed-bad events seed supervised training (noisy-label / programmatic-labeling techniques, e.g. Snorkel-style).
3. **Synthetic red-team injection** (§5.5) — controlled positives with known ground truth.
4. **The EDD feedback loop** — every investigated alert returns fraud/FP/inconclusive. **This compounds: the system you ship in month 3 with few labels becomes materially better by month 12 purely from operating it.** Use **Positive-Unlabeled (PU) learning** and **semi-supervised** methods to exploit the vast unlabeled majority.

### 5.5 Synthetic data — do it right (a researched warning)
You said you'll generate what you don't have. Two methods, used for different jobs — and **a critical pitfall**:

- **Agent-based scenario simulation (preferred for behavioural realism).** Build a PaySim/MoMTSim-style simulator that models *your* employees, roles, and the **exact typologies from your reference doc** (beneficiary-then-approve, dormant-reactivation→drain, SWIFT-without-CBS, suspense lapping, privilege self-grant→fraudulent approval, bulk export before resignation). This preserves **temporal/velocity/multi-account structure** — the thing that matters for behavioural fraud. This is your **red-team library** and your primary synthetic source.
- **Generative tabular augmentation (CTGAN / TVAE / diffusion such as EmDT) — with caution.** Useful to *oversample* rare classes for the tabular model, **but recent (2026) benchmarks show naive tabular GANs FAIL to preserve behavioural patterns** (inter-event timing, velocity, multi-account motifs) because they generate rows independently. **Rule:** use generative models only for *feature-space augmentation* of the supervised layer, and use conditional sampling / entity-aware autoregressive generation; for *behavioural* realism use the agent-based simulator. Always train the final classifier (XGBoost) on a mix that is anchored to real distributions, and never evaluate on synthetic alone.
- **Industry-standard imbalance handling:** negative subsampling at **1:3 to 1:10**, plus class weights / focal loss; calibrate afterwards.

---

## 6. Feature engineering catalogue (the heart of behavioural baselines)

This is where most of the value is created. Every red flag in your reference doc becomes one or more features. **Baselines are computed three ways simultaneously** — *per-entity* (this user vs their own history), *per-peer-group* (this user vs others in the same role/branch/dept), and *global* — each with **time decay**, so a slow drift in one is anchored by the others (this is the antidote to "low-and-slow" baseline poisoning).

### 6.1 Identity & access features
- Off-hours/odd-hours score (vs personal & peer baseline); first-time-after-hours flag
- Login velocity; failed→success bursts; impossible-travel; new-device/new-geo
- **Dormant-account reactivation → activity** (your branch-banking red flag)
- **Privilege-escalation events**; entitlement-change velocity; **acting outside one's role** (peer deviation)
- Session-duration anomaly; concurrent-session anomaly
- "No leave taken" streak (rogue-trader / vault-skimming red flag)

### 6.2 Transaction features
- Amount z-score vs personal/peer baseline; **just-under-threshold** clustering; round-number bias
- Transaction velocity in sliding windows; burst detection
- **New-beneficiary → high-value-payment latency** (the toxic-combination signal)
- **Maker-checker pairing frequency** (always-the-same-pair = collusion candidate)
- Reversal patterns clustered on one operator (reversal-theft)
- Fee/charge/rate-override frequency on linked accounts
- **Suspense/nostro item aging**; same person posting *and* reconciling
- **SWIFT↔CBS reconciliation mismatch** (the PNB mechanism — instrument with no CBS entry)
- Standing-instruction/beneficiary modification events

### 6.3 Data-layer features (the privileged "god-mode" tier)
- Download/export volume vs baseline; **bulk-export** flag; export to personal channel
- **DB write/update with no corresponding application transaction** (direct manipulation)
- Sensitive-table/PII/PAN access outside role; unusual query shapes
- Logging-configuration changes; audit-setting changes (log-tampering proxy)
- Use of shared/service/orphaned accounts; dormant privileged account activation

### 6.4 Change & HR-context features
- **Entitlement self-grant**; short-lived privilege grants timed around transactions
- Role-change recency; tenure; **leaver/notice-period flag** (exfil risk window)
- Referrer-cluster (multiple hires by one referrer landing in sensitive roles — embedded-accomplice signal)
- Toxic-combination flags: *holds conflicting entitlements*; *acted on a self-granted right*

### 6.5 Graph / relational features (feed L5)
- Degree/centrality in the beneficiary/counterparty graph
- Shared device/IP/address/phone links between employees and beneficiaries
- Circular-flow / round-tripping motifs; mule-chain patterns
- Maker-checker collusion subgraphs; employee↔customer-account linkage

### 6.6 Temporal / sequence features (feed L4)
- Behavioural drift vs rolling baseline; change-point detection
- Session action-sequences (order and timing of actions)
- Periodicity breaks (e.g., end-of-period manual journal entries)

> **Engineering note:** compute streaming features in **Flink** (sliding/tumbling windows, keyed state per entity), materialize them in **Feast/Redis** for sub-millisecond online serving, and backfill the same definitions in **ClickHouse** so training and serving use *identical* feature logic (avoid train/serve skew). Use **Deep Feature Synthesis / featuretools**-style automated aggregation to scale feature creation, as done in CERT-based studies.

---

## 7. Models, layer by layer — and the verdict on each technique

### Layer 2 — Unsupervised anomaly (cold start, no labels)
- **Isolation Forest** (fast, scalable, great default), **Autoencoder** (reconstruction error on "normal" behaviour), **ECOD/COPOD** (parameter-free, explainable), **One-Class SVM** (smaller scale). Library: **PyOD**.
- **Why:** you have no labels on day one; these flag deviations from learned "normal." Autoencoders also give a natural per-feature reconstruction-error explanation.
- **Role:** the always-on safety net for *novel* schemes that no rule and no labeled model has seen.

### Layer 3 — Supervised gradient boosting (the workhorse)
- **XGBoost / LightGBM** (LightGBM usually faster on wide tabular data; XGBoost slightly stronger regularization — benchmark both). CatBoost if many high-cardinality categoricals.
- **Why (the verdict on your question):** for **tabular, event-level** fraud scoring this is the proven best-in-class — it dominates fraud competitions and production, trains in minutes, handles missing values and mixed types, and pairs natively with **SHAP** for the "contextual explanations" your brief requires.
- **Role:** the precision engine once the feedback loop yields labels. This is where most caught fraud will actually be scored.
- Handle imbalance with class weights / `scale_pos_weight` / focal loss + 1:3–1:10 subsampling; **calibrate** with isotonic/Platt so the 0–100 score is meaningful.

### Layer 4 — Sequence / multivariate time-series
- **Unsupervised:** **USAD** (adversarially-trained autoencoders; fast, stable) and **TranAD** (transformer with focus-score self-conditioning + adversarial training; explicitly designed for *scarce labels, high volatility, ultra-low inference time* — i.e., your exact constraints). **Anomaly-Transformer** (association discrepancy) as an alternative. Simpler: **LSTM-autoencoder**, and **DeepLog/LogAnomaly** for log-sequence anomalies.
- **Explainable supervised:** **LAXCAT** — CNN feature extraction + **variable-attention** + **temporal-attention**, so it tells you *which variables* and *which time intervals* drove a classification. **Use it to explain flagged sessions once you have labels** (e.g., from EDD). It is supervised, so it is an enhancement, not a cold-start detector.
- **Why:** "low-and-slow" insiders and session-level patterns are temporal; per-event models miss them.
- **⚠️ Honest caveat (this matters):** the deep-MTS-anomaly literature is plagued by the **point-adjust evaluation protocol**, which can make even near-random scores look excellent; several "SOTA" results don't survive rigorous evaluation, and simple baselines often match them. **Do not lead with these models.** Add them only after L1–L3 are saturated, benchmark them honestly against simple baselines on *your* data with proper temporal splits, and keep them only if they earn their operational cost.

### Layer 5 — Graph / relational (collusion)
- **GraphSAGE** (inductive — handles new nodes), **GAT / heterogeneous graph attention networks**, and collusion-specific architectures (e.g., GoSage-style hierarchical-attention heterogeneous GNNs). Library: **PyTorch Geometric / DGL**. Real-world precedent: a 5M-node/10M-edge heterogeneous transaction graph at a large national bank for AML.
- **Why:** maker-checker collusion, mule networks, toxic-combination-in-practice, and insider+external rings are *relational* — they're invisible to tabular models that treat events independently. This is the layer that addresses your doc's "engineered collusion rings" (Part 7), the hardest category.
- **Note:** graph construction/maintenance and explainability are the hard parts — budget for graph data engineering and use GNNExplainer-style attribution for regulator-facing reasons.

### Layer 6 — Risk fusion
- A **stacked meta-model** (or transparent weighted ensemble) consumes the per-layer scores + rule hits and emits one **calibrated 0–100 risk score** with **severity × confidence**, plus the **contributing reason codes** (rule provenance + SHAP top features + attention/graph evidence). Prefer an interpretable fusion (logistic/GBM on layer outputs) so the final decision is itself explainable to audit.

### The escalation discipline ("work smartly")
Ship **L1 + L2 + dashboard** first (value in weeks, no labels needed). Add **L3** once the loop yields labels. Add **L4/L5** only when justified. This is how you build an enterprise system without going "all-in" on compute and complexity up front.

---

## 8. Technology stack (on-prem, fully self-hostable)

| Concern | Recommended | Why | Alternatives / notes |
|---|---|---|---|
| **Event ingestion** | **Apache Kafka** | De-facto standard; millions of events/sec; ordering, durability, replay | Redpanda (Kafka-API, C++, lower ops); RabbitMQ (smaller scale) |
| **Stream processing** | **Apache Flink** | Mature stateful streaming, keyed per-entity state, sliding windows, CEP, sub-second | **Rust option:** Arroyo/Fluvio (newer, less battle-tested); Spark Structured Streaming/Real-Time Mode |
| **Online feature store** | **Feast + Redis** | Single feature definition for train & serve; Redis = single-digit-ms serving; avoids train/serve skew | Tecton (commercial); custom Redis |
| **Rules / BRE** | **Drools** or a **Rust/Go rules-gateway** or **Flink CEP** | Deterministic, explainable, hot-reloadable SoD/toxic-combination matrix | Open-Policy-Agent for entitlement logic |
| **ML training & experimentation** | **Python**: scikit-learn, **XGBoost/LightGBM**, **PyTorch**, **PyOD**, **PyTorch Geometric**, featuretools | The ML ecosystem; nothing serious competes here | — |
| **Model serving / inference** | **ONNX Runtime** or **NVIDIA Triton** (or **BentoML**) | Low-latency, language-agnostic; export trees & nets to ONNX | **Rust inference:** `ort` (ONNX Runtime bindings) or `candle` for the hot path |
| **Analytical / investigation store** | **ClickHouse** | Columnar, ingests millions/sec, sub-second queries over **billions–trillions** of events, hot-cold tiering, inverted indices for log search. **Exabeam (UEBA) and IBM QRadar (SIEM) both run security analytics on ClickHouse** — your instinct was right | Apache Druid/Pinot (real-time OLAP); Elastic (heavier, costlier) |
| **Search** | ClickHouse inverted indices | Token search co-located with analytics | OpenSearch if you need full Lucene |
| **Batch / retraining orchestration** | **Airflow** or **Dagster** | Schedule retraining, backfills, slow-lane jobs | Argo Workflows on K8s |
| **Experiment tracking + model registry** | **MLflow** | Versioning, lineage, champion/challenger | Weights & Biases (self-hosted) |
| **Drift & quality monitoring** | **Evidently** + Prometheus/Grafana | Data + concept drift; model-degradation alerts | Custom PSI/KS monitors |
| **Investigator dashboard** | **React + TypeScript** on a **ClickHouse** backend (API in Rust/Go/Python) | Sub-second drill-down; bespoke triage UX | Grafana/Superset/Metabase for ops dashboards |
| **Audit/immutability** | Append-only **Kafka audit topics** + WORM storage | Tamper-evident regulator trail | Object-lock on on-prem object store |
| **Orchestration/runtime** | **Kubernetes** (on-prem) or VMs | Scale, HA, rolling deploys | — |

### Where Rust fits (precisely)
You named Rust; here is its honest, valuable role. **Rust is excellent for the latency-critical, memory-safe service tier** — the **ingestion/enrichment gateway**, the **rules/scoring gateway**, and the **online inference service** (via `ort`/`candle`). It buys you predictable low latency and safety at high throughput. **Rust is *not* where the ML lives** — training, experimentation, and the model zoo are Python. A clean split: **Rust/Go for the hot-path services, Python for ML, Flink (JVM) for stateful streaming, ClickHouse for analytics.** If the team strongly prefers Rust end-to-end on streaming, Arroyo is a Rust-native option — but Flink is more battle-tested for a bank.

### Where ClickHouse fits (precisely)
ClickHouse is the **investigation and analytics backbone**, not the real-time scoring path (that's Flink+Redis). It stores the full event history for **investigator drill-down, entity-360 timelines, backtesting/replay, and feature backfill**, with hot-cold tiering (e.g., 14–30 days hot). It is open-source and self-hostable → **fits on-prem and India data-localization perfectly.**

---

## 9. Infrastructure & deployment (on-prem PSB)

### 9.1 Reference topology
```
            ┌──────────────┐   read-only feeds   ┌─────────────────────────────────────┐
 CBS/SWIFT  │ Source systems│────────────────────▶│ Collectors/agents → Kafka cluster   │
 IAM/PAM    │ (existing)    │                     │ (3–5 brokers, replicated)           │
 DB audit   └──────────────┘                     └───────────────┬─────────────────────┘
 HR/IGA                                                          ▼
                                              ┌──────────────────────────────────────────┐
                                              │ Flink cluster (stateful enrichment +      │
                                              │ windowed features + CEP rules)            │
                                              └───────┬───────────────────────┬───────────┘
                                                      ▼                       ▼
                                      ┌────────────────────────┐   ┌────────────────────────┐
                                      │ Redis/Feast (online     │   │ Model-serving nodes     │
                                      │ features, sub-ms)       │   │ (ONNX/Triton; GPU for   │
                                      └────────────────────────┘   │ training & graph, CPU   │
                                                      │             │ for inference)          │
                                                      ▼             └───────────┬─────────────┘
                                      ┌────────────────────────────────────────▼─────────────┐
                                      │ Risk fusion service → alerts topic → Case/Alert store │
                                      └───────────────────────┬───────────────────────────────┘
                                                              ▼
   ┌──────────────────────┐     queries/drill-down    ┌──────────────────────────────────────┐
   │ Investigator dashboard│◀──────────────────────────│ ClickHouse cluster (hot+cold, history,│
   │ (React/TS)           │                            │ search, backfill) + audit/WORM        │
   └──────────────────────┘                            └──────────────────────────────────────┘
   Cross-cutting: K8s, HSM for keys, Prometheus/Grafana, MLflow, Airflow/Dagster, network segmentation
```

### 9.2 Sizing (order-of-magnitude, large-PSB scale)
For tens of millions of transactions/day plus access/DB/HR telemetry (often 5–20× the transaction volume in raw events):
- **Kafka:** 3–5 brokers (replication factor 3), partitioned by entity for parallelism.
- **Flink:** start with a handful of task managers; scale by keyed-state size and event rate.
- **ClickHouse:** a small sharded+replicated cluster; **hot-cold tiering** keeps recent data on fast disk, ages the rest to cheaper storage; expect heavy compression (security log data compresses ~10–20×).
- **GPU:** a small pool for training the deep sequence/graph models and periodic retraining; **inference is mostly CPU** (trees + small nets via ONNX).
- **Redis:** sized to hold per-entity online features for the active population.

### 9.3 Security, residency, resilience
- **Data residency:** everything in-India data centre(s) per RBI localization. No data leaves the perimeter; no managed-cloud ML.
- **Security:** network segmentation; service accounts at least privilege; **integrate with PAM** for the system's own admin access; field-level encryption for PII; **HSM** for keys; RBAC on the dashboard (analysts see only assigned cases).
- **Immutability:** all alerts, dispositions, model versions, and feature snapshots to **append-only/WORM** storage — your regulator and Internal Audit trail.
- **HA/DR:** multi-rack/multi-DC replication for Kafka/ClickHouse; documented RPO/RTO; regular restore drills.
- **Integration points:** read-only from CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR; **bi-directional with the SIEM** (consume logs, publish alerts); **feed the RBI EWS/CRILC** pipeline for slow-lane red-flagged accounts.

---

## 10. MLOps & the feedback loop (what makes it improve)

1. **Training pipeline (Airflow/Dagster):** pull labeled + unlabeled features from ClickHouse/Feast → train L2/L3/L4/L5 → validate → register in MLflow.
2. **Shadow → champion/challenger → canary:** every new model runs in **shadow mode** (scores live traffic, no alerts) until it beats the champion on *your* metrics; promote gradually.
3. **The EDD feedback loop (core):** alert → investigator disposition → labeled store → **active learning** (prioritize uncertain/high-value cases for labeling) → scheduled retrain → A/B. This is the compounding engine: operating the system *is* how it gets smarter.
4. **Drift detection:** monitor data drift (PSI/KS on features) and concept drift (rolling precision/recall on dispositions); alert and trigger retraining when the population shifts (new products, reorg, seasonality).
5. **Threshold & alert-volume governance:** the binding constraint is **analyst capacity**. Tune the alert threshold to your team's daily throughput; track **precision@k**, **alert-to-true-fraud ratio**, and **mean-time-to-disposition**; budget alerts, don't flood.
6. **Model governance (RBI / SR 11-7-style):** versioning, independent validation, documented assumptions, **bias/fairness checks** (no disparate flagging by department/grade beyond risk-justified), and **explainability artifacts** retained for audit. Treat models as regulated assets.
7. **Backtesting/replay:** stream historical ClickHouse events back through candidate models to estimate detection lift and false-positive cost before deployment.

---

## 11. The investigator dashboard (the frontend)

Your brief: *"offer a dashboard for the fraud investigation team to triage and act on cases efficiently."* Design it around the investigator's actual workflow.

**Core views**
- **Triage queue:** alerts ranked by fused risk × monetary exposure × confidence; deduplicated per entity; SLA/TAT timer (RBI prefers ≤30-day examination).
- **Entity-360:** one screen unifying the actor's transactions, access events, DB/data activity, and HR context on a single **timeline** — the joined-up view no analyst can assemble by hand.
- **Explanation panel:** *why this fired* — rule provenance (which SoD/typology), **SHAP** top contributing features, sequence **attention** (LAXCAT) for sessions, and graph evidence for collusion. This is the "contextual explanations" requirement, made real and **defensible for SAR/FMR filing**.
- **Graph/link view:** beneficiary networks, shared-device/address links, maker-checker collusion subgraphs.
- **Peer comparison:** this user vs their peer group on the flagged dimension (makes "abnormal" concrete and fair).
- **Action & EDD:** escalate / request-block / close-as-FP / mark-fraud / add-notes, with a structured **EDD checklist**; every action is captured as a **label** and written to the immutable audit log.
- **Reporting:** one-click **CRILC/FMR**-ready case export; management KRI dashboards; trend/coverage views for the SCBMF/board.

**Stack:** **React + TypeScript** front end over a **ClickHouse** backend (sub-second drill-down across billions of events), API in **Rust/Go/Python**; **Grafana** for ops/health dashboards. ClickHouse is the right choice here precisely because investigation means ad-hoc, high-cardinality queries over long history — its strength, and why security vendors build their consoles on it.

---

## 12. Detection coverage map (does it "solve each and everything"?)

Honest mapping of the doc's fraud vectors to how this system catches them — and where it can't fully, in real time.

| Fraud vector (from your doc) | Caught by | Key features / signals | Lane |
|---|---|---|---|
| Reversal theft (branch) | L1 + L2 | reversal clustering per operator; deposit-then-reverse pattern | Fast |
| Dormant-account takeover | L1 + L2 | reactivation→activity; silent channel enrollment | Fast |
| Beneficiary-then-approve (toxic combo) | L1 + L3 + L5 | new-beneficiary→high-value latency; maker-checker pairing | Fast |
| SWIFT/LoU abuse (PNB mechanism) | **L1** | **SWIFT↔CBS reconciliation mismatch** (instrument with no CBS entry) | Fast |
| Suspense/nostro lapping | L1 + L2 | item aging; same person posts & reconciles | Fast/Slow |
| Rogue trading (mismarking, fictitious trades) | L1 + L2 + L4 | won't-take-leave; late/cancelled-rebooked trades; P&L-vs-mark divergence | Fast/Slow |
| Direct DB manipulation (privileged) | **L1 + L2** | **DB write with no app txn**; off-hours; out-of-scope access | Fast |
| Entitlement self-grant / temp admin | L1 | short-lived grants timed to transactions | Fast |
| Log tampering / control disablement | L1 | audit-config changes; logging gaps | Fast |
| Bulk data exfiltration | **L1 + L2 + L4** | download volume vs baseline; export to personal channel; leaver-window | Fast |
| Fake-vendor / billing | L1 + L3 + L5 | vendor=employee address; round/sequential invoices; single-client vendor | Fast/Slow |
| Alert suppression (AML watchers) | L2 + L3 | one analyst clearing disproportionate share; reopened-then-cleared | Slow |
| Ghost employees / payroll | L1 + L3 + L5 | no tax footprint; duplicated bank details | Slow |
| Collusion rings / embedded accomplices | **L5** | maker-checker subgraphs; referrer-cluster hiring; shared-identity links | Slow |
| Ghost/insider loans, inflated appraisal (credit) | **Slow lane** | thin docs; appraiser-is-borrower; disbursement-to-non-sanctioned-account | **Slow** |
| Executive financial-statement fraud / override | **Partial** | always-hits-target; close-control overrides; cultural KRIs | **Slow + non-technical controls** |

**The honest limits (state these to stakeholders):**
- **Credit/loan fraud is slow-lane only** — it surfaces over weeks/months via entity and document signals feeding EWS; it is *not* a real-time win. The system *accelerates* it (forensic-audit-in-years → red-flag-in-weeks) but doesn't make it instant.
- **Executive override and pure human collusion with no digital footprint** are only partially addressable by *any* system — they still need culture, whistleblowing, surprise audit, and board oversight (your doc's point, and the ACFE's). Don't oversell this.
- **A determined low-and-slow insider** can still shift a baseline gradually; mitigated (not eliminated) by peer-anchoring, long windows, and change-point detection.

---

## 13. Phased implementation plan (the procedure)

A realistic sequencing that delivers value early and avoids "all-in" risk.

**Phase 0 — Foundations (≈ weeks 0–8)**
- Stand up Kafka + ClickHouse + the **unified event model**; ingest 1–2 highest-signal sources (transactions + IAM/PAM).
- Build the **Layer-1 BRE** with your SoD/toxic-combination matrix and the top known typologies (SWIFT↔CBS mismatch, new-beneficiary→high-value, DB-write-without-app-txn, dormant-reactivation, entitlement self-grant).
- Run in **shadow mode**; begin the synthetic scenario library.
- *Exit metric:* end-to-end event flow; rules firing with full explainability; baseline alert volume measured.

**Phase 1 — UEBA + cold-start ML + dashboard MVP (≈ months 2–5)**
- Compute per-entity/per-peer **behavioural baselines**; deploy **Layer-2** (Isolation Forest + autoencoder via PyOD).
- Ship the **investigator dashboard MVP** (triage queue, entity-360, explanation panel) and the **EDD feedback capture**.
- Expand telemetry to data-layer + change/HR.
- *Exit metric:* analysts working real alerts; feedback loop producing labels; precision@k tracked.

**Phase 2 — Supervised precision + full features (≈ months 5–9)**
- Train **Layer-3 XGBoost/LightGBM** on accumulated labels (EDD + known cases + synthetic + rule-weak-labels); add SHAP reason codes.
- Complete the feature catalogue; tune thresholds to analyst capacity; calibrate scores.
- *Exit metric:* measurable lift in precision and earlier detection vs Phase-1; false-positive burden down.

**Phase 3 — Sequence, graph, slow lane, compliance (≈ months 9–15)**
- Add **Layer-4** (USAD/TranAD for low-and-slow; LAXCAT for session explanations) — *only after honest benchmarking*.
- Add **Layer-5** graph/collusion (PyG/DGL); build the **slow-lane credit/entity module** feeding RBI **EWS/CRILC**.
- Mature model governance, drift monitoring, and FMR/CRILC reporting.
- *Exit metric:* collusion and slow-burn coverage live; full regulatory reporting integrated.

**Phase 4 — Continuous improvement (ongoing)**
- Active-learning retraining cadence; periodic **red-team exercises** (inject synthetic typologies to measure detection); model-risk reviews; coverage expansion.

---

## 14. Metrics & evaluation (measure it honestly)

**Detection quality (use the right metrics for extreme imbalance):**
- **PR-AUC / average precision** (not ROC-AUC alone — ROC-AUC flatters imbalanced data).
- **Precision@k** and **alert-to-true-fraud ratio** (what fraction of alerts are real).
- **Recall on known historical cases** (would it have caught the ones you know about?).
- **Time-to-detection reduction** vs the status-quo (the headline business metric).

**Operational:**
- Alert volume vs analyst capacity; **mean-time-to-disposition**; false-positive rate; RBI **TAT** (≤30-day) compliance.

**Business:**
- Estimated loss avoided / caught-earlier; cases surfaced by system vs by tips (move the needle on the ACFE "tips dominate" reality).

**Evaluation pitfalls to *avoid* (researched, and they bite hard):**
- **Point-adjust inflation** on time-series anomaly metrics — can make random scores look great; use rigorous, non-point-adjusted evaluation.
- **Data leakage** — e.g., PaySim's balance columns, or any feature that encodes the label.
- **Temporal leakage** — always split train/test by *time* (past→future), never randomly; fraud detection is a forecasting problem.
- **Synthetic-only evaluation** — synthetic is for training/augmentation; validate detection quality against *real* labeled outcomes.

---

## 15. Risks, pitfalls & honest limitations

- **Adversarial insiders who know the thresholds.** Mitigate: don't expose logic; use **peer-relative** (not absolute) baselines; add controlled randomization to review sampling; emphasize unsupervised novelty detection.
- **Low-and-slow baseline poisoning.** Mitigate: long observation windows; **peer-group anchoring**; change-point detection; periodic baseline resets reviewed by humans.
- **Alert fatigue.** Mitigate: **L6 fusion** (one alert per entity), ranking by exposure, alert budgeting, and the feedback loop tuning precision. This is the #1 operational killer of fraud systems — design against it from day one.
- **Privacy, employee surveillance & fairness.** This system watches staff. Mitigate: **proportionality** (monitor risk-relevant signals, not everything), **transparency** with staff/works-council/HR/legal, fairness testing, strict RBAC, and **human-in-the-loop with natural justice** before any classification. Get this wrong and you have a legal/cultural problem, not just a technical one.
- **Collusion & executive override remain partly out of reach.** No model fully solves the "two honest-looking people defeating dual control" or "the CEO overrides the control" problems — your doc's hardest cases. Pair the system with the human controls (whistleblowing, surprise audit, board oversight).
- **Cold start.** Mitigate: rules + synthetic + transfer-learning carry the first months; the feedback loop does the rest.
- **Model risk & explainability for regulators.** Mitigate: governance, calibration, retained explanation artifacts, independent validation.
- **The "no silver bullet" truth.** This dramatically raises detection speed and coverage for digitally-observable insider fraud and gives investigators superpowers — but it complements, not replaces, tips, audit, segregation of duties, and culture. Set that expectation with leadership explicitly.

---

## 16. Compliance & governance (India / RBI)

The system must *fit* the regulatory machinery your doc describes:
- **RBI Master Directions on Fraud Risk Management (July 15, 2024):** support the **Early-Warning-Signal (EWS)** framework *integrated with CBS* and extended to non-credit/digital activity; tag **Red-Flagged Accounts (RFA)**; respect the **CRILC** ₹3-crore / 7-day reporting and the **180-day** classification window; produce **Fraud Monitoring Returns (FMR)** and feed the **Central Fraud Registry (CFR)**; support the **Data Analytics & Market Intelligence Unit** mandate. The slow lane is explicitly your EWS engine.
- **Natural justice (SBI v. Rajesh Agarwal, 2023):** the system **flags and evidences**; it never auto-classifies fraud — a human, with the accused's hearing, does. Your alert-only design is *required*, not just prudent.
- **Data localization (RBI, 2018):** all data and compute **on-prem in India** — already your constraint.
- **Model governance:** version control, independent validation, bias/fairness review, immutable audit, retained explanations — treat ML models as regulated assets subject to the same scrutiny as any other control.

---

## 17. Quick-reference appendices

### A. Model-by-layer cheat sheet
| Layer | Job | Models | Labels needed? |
|---|---|---|---|
| L1 Rules/BRE | Known typologies, SoD | Deterministic rules / CEP | No |
| L2 Unsupervised | Cold-start novelty | Isolation Forest, Autoencoder, ECOD/COPOD (PyOD) | No |
| L3 Supervised | Precision event scorer | **XGBoost / LightGBM** + SHAP | Yes |
| L4 Sequence | Low-and-slow, sessions | USAD, TranAD, Anomaly-Transformer; **LAXCAT** (explainable, supervised) | Mixed |
| L5 Graph | Collusion / rings | GraphSAGE, GAT, hetero-GNN (PyG/DGL) | Semi |
| L6 Fusion | One calibrated score + reasons | Stacked/weighted ensemble | Yes |

### B. Dataset cheat sheet
- **Insider prototyping:** CMU-SEI **CERT** (r4.2/r5.2/r6.2), SPEDIA.
- **Tabular fraud prototyping:** **IEEE-CIS**, ULB **Credit-Card-Fraud**, Fraud-Dataset-Benchmark.
- **Scale testing:** **PaySim** (mind the leakage).
- **Graph prototyping:** **Elliptic**.
- **Production signal:** your telemetry + agent-based synthetic red-team library + EDD feedback labels. **No drop-in pre-trained model exists for your bank.**

### C. Tech-stack cheat sheet
Kafka → Flink → Feast/Redis → Python(XGBoost/LightGBM/PyTorch/PyOD/PyG) → ONNX/Triton → **ClickHouse** → React/TS dashboard. **Rust** for the ingest/rules/inference gateways. All **self-hostable, on-prem, India-localized.**

### D. Key references (for the team to read)
- ACFE — *Occupational Fraud 2024: Report to the Nations* (base rates, detection-by-tips).
- RBI — *Master Directions on Fraud Risk Management* (2024); *SBI v. Rajesh Agarwal* (2023).
- CMU-SEI **CERT** Insider Threat dataset & papers; *Deep Learning for Insider Threat Detection: Review* (arXiv 2005.12433).
- **USAD** (KDD 2020); **TranAD** (VLDB 2022, arXiv 2201.07284); **Anomaly Transformer** (ICLR 2022); *Towards a Rigorous Evaluation of Time-Series Anomaly Detection* (the point-adjust critique).
- **LAXCAT** — *Explainable Multivariate Time Series Classification* (Hsieh, Wang, Sun, Honavar, 2020; arXiv 2011.11631).
- *Graph Neural Networks for Financial Fraud Detection: A Review* (arXiv 2411.05815); **safe-graph/graph-fraud-detection-papers** (GitHub); *Finding money launderers using heterogeneous GNNs* (DNB, 2025).
- IEEE-CIS / ULB Credit-Card / PaySim / Elliptic dataset pages; *Fraud Dataset Benchmark* (Amazon, arXiv 2208.14417).
- ClickHouse for security analytics (Exabeam, IBM QRadar case studies); Kafka+Flink real-time fraud architecture references.
- Vendor framings to study (and surpass): Feedzai *RiskOps/TRUST*, Featurespace *Adaptive Behavioral Analytics*, NICE Actimize, DataVisor (unsupervised), Securonix/Exabeam (UEBA).

---

*Built around your reference document's taxonomy and confirmed scope (real production system, on-prem/India-localized, alert-only → human EDD → block, real-time insider/privileged behaviour first, full telemetry, real + synthetic data). The fast lane is the primary build; the slow lane (credit/entity/EWS) is phased. The system's purpose is to collapse detection time and give investigators a unified, explainable, prioritized view — not to promise the impossible.*

---
---

# ADDENDUM (appended on request)
### Parts 18–20: Inference Pipeline · Cybersecurity & Vulnerability Management · Per-Layer Technique Selection (deep research)

> Nothing above was removed. These three parts extend the blueprint with (18) the full inference pipeline, (19) a complete security/cybersecurity and vulnerability-management programme for the system itself, and (20) a research-paper-grounded, head-to-head justification for the model chosen at **each** layer — with reasoning on why it beats the alternatives, recommended starting parameters, and paper sources.

---

## PART 18 — THE INFERENCE PIPELINE (online + batch)

The system runs **two inference paths** sharing one feature definition and one model registry: a **real-time (online) path** that scores every event in milliseconds, and a **batch (scheduled) path** for the heavier sequence/graph/slow-lane models. Keeping both paths on the *same* feature logic (via Feast) is what prevents train/serve skew.

### 18.1 Real-time (online) inference path — per event

```
 event ──▶ Kafka(topic: events) ──▶ Flink(enrich + window features) ──┐
                                                                       │  (feature read/write)
                                                          Redis/Feast online store ◀──┘
                                                                       │
         ┌─────────────────────────────────────────────────────────────┘
         ▼
  L1 RULES gateway (Rust/Go or Flink-CEP)  ── hard hit? ──▶ emit HIGH alert immediately (skip ML)
         │  (no hard hit → assemble feature vector)
         ▼
  Model-serving (ONNX Runtime / Triton):  L2 unsupervised score  +  L3 GBDT score  (+ L4 session score if window mature)
         │
         ▼
  L6 FUSION service: calibrated 0–100 score + severity×confidence + reason codes (TreeSHAP, inline)
         │
         ├──▶ Kafka(topic: alerts) ──▶ Alert/Case store ──▶ Investigator dashboard
         ├──▶ ClickHouse (event + score + features persisted for investigation/replay)
         └──▶ Feature snapshot persisted (for reproducibility & later labels)
   Async: entity/edge updates ──▶ Graph store ──▶ L5 GNN/XGB-Graph scored in near-real-time/batch ──▶ may raise/upgrade alert
```

**Latency budget (target end-to-end ≤ ~100–300 ms for the alert decision; this is alert-only, not in the payment path, so it is comfortable):**
- Kafka ingest + Flink enrichment: ~10–40 ms
- Online feature lookup (Redis): ~1–5 ms
- L1 rules: <5 ms
- L2+L3 model inference (trees via ONNX): ~5–30 ms (trees are extremely fast; this is why GBDTs are ideal online)
- TreeSHAP reason codes: ~5–20 ms (use plain TreeSHAP, **not** interaction values — those are ~quadratic in features and belong offline)
- Fusion + emit: ~5–10 ms

**Design rules for the online path**
- **Trees in the hot path, deep nets out of it.** L2/L3 (Isolation Forest, autoencoder, GBDT) score inline; L4 sequence and L5 graph models run on session-close or on a short async cadence and *upgrade* an existing alert rather than blocking the hot path. This keeps p99 latency predictable.
- **Exactly-once / idempotency:** key events by a deterministic event_id; use Flink checkpointing and Kafka transactions so a replay doesn't double-alert.
- **Backpressure & graceful degradation:** if the model server is unavailable, **fall back to L1 rules only** and mark those events for re-scoring — the system never goes dark, it degrades to rules.
- **Caching:** cache per-entity baselines and peer-group statistics in Redis with TTLs; recompute on a schedule, not per event.
- **Shadow scoring:** every challenger model scores live traffic in parallel (no alerts) so you can compare before promotion.

### 18.2 Batch / scheduled inference path
Runs on Airflow/Dagster at cadences matched to each detector's horizon:
- **L4 deep sequence (USAD/TranAD)** — score per-entity session/day windows (e.g., every 15 min to hourly).
- **L5 graph (XGB-Graph / GraphSAGE / specialized GNN)** — rebuild/refresh the entity graph and re-score (e.g., hourly to daily depending on graph size; incremental for new nodes via inductive GraphSAGE).
- **Slow-lane entity/credit scoring** — daily/weekly; feeds the RBI EWS/CRILC pipeline.
- **Periodic re-scoring** of recent events when a model is retrained (backfill from ClickHouse).

### 18.3 Model serving & lifecycle
- **Packaging:** export trees and nets to **ONNX**; serve via **ONNX Runtime** (CPU, low-latency) or **Triton** (mixed CPU/GPU, dynamic batching for the deep models). Optional **Rust** inference service (`ort`/`candle`) for the latency-critical gateway.
- **Registry & versioning:** **MLflow** holds every model version, its training data hash, features, metrics, and the approving reviewer (audit requirement).
- **Champion/challenger + canary:** promote only after a challenger beats the champion on *your* metrics in shadow; roll out by canary percentage with automatic rollback on metric regression.
- **Reproducibility:** persist the exact feature vector and model version with every score, so any alert can be reconstructed months later for audit / natural-justice proceedings.
- **Drift-triggered retraining:** Evidently/PSI monitors fire retraining when feature or concept drift crosses thresholds.

---

## PART 19 — CYBERSECURITY, ADVERSARIAL ROBUSTNESS & VULNERABILITY MANAGEMENT

> **Why this part is non-negotiable.** This system is, by design, the single most attractive internal target in the bank. It holds the **crown jewels** (the unified behavioural record of every employee and privileged user, plus PII/PAN it must read), and it is **the one system a sophisticated insider most wants to blind, poison, or evade.** A fraud-detection platform that is itself insecure doesn't just fail — it becomes a new toxic-combination and a single point of catastrophic compromise. The irony to state plainly to leadership: *a system that watches privileged users is itself operated by privileged users, and must hold itself to a stricter standard than anything it monitors.*

### 19.1 Threat model (STRIDE + insider lens + ML-specific)
Model the system with **STRIDE** (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) **and** the **MITRE ATLAS** framework for AI-specific attacks. Three attacker classes: (a) **external** attacker who breaches the perimeter; (b) **malicious insider** with some access to the platform, its data, or its labels; (c) **the subjects themselves** — employees/privileged users trying to evade detection.

### 19.2 ML-specific attacks and mitigations (mapped to MITRE ATLAS)
MITRE ATLAS is the ATT&CK-equivalent knowledge base for attacks on ML systems (tactics from Reconnaissance → ML Attack Staging → Exfiltration → Impact). The relevant techniques here:

| Attack (ATLAS family) | What it looks like for *this* system | Mitigation |
|---|---|---|
| **Evasion / adversarial perturbation** | An insider who knows the model crafts activity to stay just under detection (your doc's "insiders know the thresholds") | **Peer-relative** (not absolute) baselines; don't expose thresholds/logic; randomized review sampling; ensemble of diverse detectors (rules + unsupervised + supervised + graph) so evading one doesn't evade all; adversarial-robustness testing |
| **Data / label poisoning** | A privileged user with data access slowly corrupts training data, or **poisons the behavioural baseline ("low-and-slow")**, or games the **EDD feedback labels** to teach the model their fraud is "normal" | **Segregate** who can touch training data vs who labels vs who builds models; provenance/lineage on all training data; anomaly-check the training set itself; peer-anchored + change-point baselines resist gradual poisoning; review label distributions for manipulation; immutable label audit |
| **Model inversion / membership inference** | Attacker queries or extracts the model to **recover sensitive customer/employee data** (a documented fraud-model risk) | Restrict inference API access (internal only, authenticated, rate-limited); avoid exposing raw scores externally; differential-privacy / regularization where feasible; monitor for extraction-pattern querying |
| **Model extraction / theft** | Stealing the model (IP + enables offline evasion crafting) | Model artifacts encrypted at rest, signed, access-controlled; no model leaves the perimeter; access logging on the registry |
| **Explanation manipulation** | Adversarial "scaffolding" classifiers can **fool LIME/SHAP into innocuous explanations** (Slack et al. 2020) | Don't rely solely on post-hoc explanations; prefer inherently interpretable components and **rule provenance**; cross-check explanations against rules and raw evidence; consider causal/invariant methods that resist forged correlations |
| **ML supply-chain compromise (AML.T0048)** | Malicious code/data in a dependency, container, or pretrained artifact | SBOM, dependency/CVE scanning, model signing, container scanning, pinned/vetted deps from an **internal mirror** (egress is off) |

### 19.3 Platform & infrastructure security (the system itself)
- **Network:** strict segmentation/micro-segmentation; the platform in its own security zone; **zero-trust** between components; no internet egress (already your posture) — all updates via an internal vetted mirror.
- **Identity & privileged access (critical):** the system's **own** admins go through **PAM** with session recording; **least-privilege** service accounts (no standing admin); **no shared/service accounts** acting anonymously (the exact anti-pattern the system is built to catch); **strong SoD inside the team** — the person who can deploy models cannot also label data or close their own alerts.
- **Data protection:** encryption **in transit (mTLS)** and **at rest**; **field-level encryption / tokenization / masking** of PII/PAN so investigators see only what they need; **HSM** for keys; **data minimization** and retention limits aligned to RBI.
- **Tamper-evident audit (quis custodiet):** **append-only / WORM** logging of *all* system activity **including the investigators' own actions** — who viewed which employee, who closed which alert, who changed a rule or threshold. The watchers must themselves be watched.
- **Dashboard:** **RBAC + need-to-know**; analysts see only assigned cases; every view/action logged; session controls.
- **Resilience:** HA + DR for Kafka/ClickHouse; tested restores; the audit log replicated and immutable.

### 19.4 Supply-chain & secure-SDLC (DevSecOps)
- **SBOM** for every build; **dependency & CVE scanning** (e.g., Trivy/Grype/OWASP Dependency-Check) gating CI; **container image scanning**; **model signing** and signature verification on load.
- **SAST/DAST/IAST**, **secrets scanning**, and **IaC scanning** in the pipeline; pinned dependencies pulled from an **internal artifact registry** (because egress is disabled).
- **Threat modeling per release**; **penetration testing**; **ATLAS-based red-teaming** that explicitly attempts evasion, poisoning, inversion, and extraction against the deployed models — not just the network.

### 19.5 Vulnerability-management programme
- **Continuous scanning** of OS, containers, dependencies, and ML artifacts; risk-ranked remediation with **patch SLAs** (e.g., critical ≤ 7 days).
- **Patching in an egress-off environment:** maintain an **internal mirror** of vetted OS/package/model updates; scheduled patch windows; emergency-patch path for criticals.
- **Adversarial-ML evaluation as a recurring control:** periodically re-test models against evasion/poisoning (this is a *vulnerability class*, not a one-off).
- **Logging & detection of attacks on the system:** monitor for extraction-pattern querying, abnormal label edits, training-data anomalies, and config/threshold changes (treat the detection platform like any other crown-jewel asset in your SIEM).

### 19.6 Governance & privacy
- **Model risk management** (independent validation, documented assumptions, bias/fairness testing) per RBI/SR-11-7-style expectations.
- **Privacy & proportionality:** the system monitors staff — process it through legal/HR/works-council review; minimize, justify, and explain monitoring; retain the **natural-justice** human-in-the-loop before any fraud classification.
- **Separation of duties within the programme itself:** build vs label vs act vs administer are different people with different access — so the anti-fraud system can never be quietly turned against the bank or an individual.

**Frameworks to align to:** MITRE ATLAS (AI threats), OWASP ML Top 10 / OWASP Top 10, NIST AI RMF and NIST CSF, plus your RBI cyber-security and IT-governance directions.

---

## PART 20 — PER-LAYER TECHNIQUE SELECTION (deep research, head-to-head)

> **How to read this.** For each layer: the **candidates**, the **benchmark evidence** (from large comparative studies that each pit 10–70+ methods against each other, plus primary papers), the **verdict**, **why it beats the alternatives**, **recommended starting parameters** (tune on your data — these are defaults, not gospel), and **sources**. The recurring meta-lesson across every rigorous benchmark below is the same and it is the single most important thing to internalize: **for tabular, anomaly, and even graph fraud detection, simpler and tree-based methods consistently match or beat the fancy deep models once evaluation is done honestly — while being faster, cheaper, and easier to explain.** This is *good news* for an on-prem enterprise build, and it is exactly the "work smartly, don't go all-in" discipline you asked for.

### 20.0 Evaluation methodology (so the verdicts are defensible)
- **Anchor on comparative benchmarks, not single-method papers.** A paper proposing method X almost always shows X winning; large independent benchmarks that re-implement and compare many methods under one protocol are far more trustworthy. The four anchors are **ADBench** (anomaly, 30 algos × 57 datasets), **Grinsztajn et al.** (tabular, RF/GBDT vs deep, 45 datasets), **TimeEval** (time-series anomaly, 71 algos × 967 datasets), and **GADBench** (graph anomaly, 29 models × 10 datasets).
- **Distrust point-adjust (PA).** For time-series anomaly detection, the PA evaluation protocol is documented to massively inflate scores (a random baseline can "beat" SOTA under PA). Verdicts below explicitly discount PA-only results.
- **Metrics for extreme imbalance:** prefer **AUPRC / average precision**, **Rec@K**, and range/affiliation-aware metrics over plain accuracy or ROC-AUC.
- **No-free-lunch is real:** ADBench's headline is that *no single algorithm dominates across datasets*. So the recommendations are "best **default** + a short benchmarking shortlist for your data," not "the one true model."

---

### 20.1 Layer 1 — Rules / Business-Rules-Engine
**Candidates:** pure rules; pure ML; **hybrid rules + ML**.
**Evidence:** Across the production fraud literature and the vendor landscape (Feedzai, Featurespace, Hawk:AI all ship rules **and** ML), the consistent finding is that **rules and ML are complements, not substitutes** — rules give deterministic coverage of *known* typologies, instant explainability, and regulator-friendliness; ML generalizes to *novel* patterns. Hybrid event-driven pipelines (Kafka+Flink+rules+ML) report sub-second latency with low false positives in recent studies.
**Verdict:** **Hybrid.** Keep a first-class **deterministic rule layer** encoding your SoD/toxic-combination matrix and known red flags (SWIFT↔CBS mismatch, new-beneficiary→high-value, dormant-reactivation→drain, DB-write-without-app-txn, entitlement self-grant). It is not an ML choice — it is the cheap, explainable, always-correct floor that the ML layers build on.
**Why over alternatives:** pure rules miss novel/under-threshold fraud (your doc's core critique); pure ML is unexplainable for the "we already know this is bad" cases and can't encode hard compliance logic. Rules also handle cold start (day 1, no labels).
**Implementation:** Drools, a Rust/Go rules-gateway, or Flink-CEP; hot-reloadable; every rule versioned and audited.
**Sources:** event-driven Kafka/ksqlDB/Flink fraud pipelines (IJERT 2026; Conduktor 2026); vendor architectures (Feedzai RiskOps, Featurespace ARIC, Hawk:AI "AI Explainable").

---

### 20.2 Layer 2 — Unsupervised anomaly detection (cold start)
**Candidates:** Isolation Forest, LOF, kNN, HBOS, CBLOF, COF, SOD, **COPOD**, **ECOD**, PCA, OCSVM, LODA, **DeepSVDD**, DAGMM, autoencoder/VAE.
**Evidence — ADBench (Han et al., NeurIPS 2022; 30 algorithms, 57 datasets, 98,436 experiments):** (1) **No unsupervised method statistically dominates** ("no free lunch"). (2) **Simple, classical detectors (Isolation Forest, ECOD, COPOD, HBOS, CBLOF, PCA) are competitive with — and frequently beat — deep unsupervised methods (DeepSVDD, DAGMM)**, while being orders of magnitude faster and having far fewer knobs. (3) **Even a little supervision beats the best unsupervised method**, which is why your EDD feedback loop matters so much. Corroborated by TimeEval (a PCA baseline "surprisingly outperforms many recent deep-learning approaches") and the broader "deep AD is often not worth it" finding.
**Verdict:** **Isolation Forest as the primary default**, with **ECOD/COPOD as parameter-free companions** and an **autoencoder** added only where you need per-feature reconstruction-error explanations or to model complex non-linear "normal." Run 2–3 in an ensemble and fuse.
**Why over alternatives:** Isolation Forest is fast (linear time, low memory), scales to your volumes, needs almost no tuning, handles high-dimensional mixed features, and is robust — exactly what cold-start production needs. ECOD/COPOD are **parameter-free** (nothing to tune, fully reproducible, easy to defend to audit). Deep unsupervised methods (DeepSVDD/DAGMM) cost far more to train/serve and **do not reliably win** in ADBench — a bad trade for production.
**Recommended starting parameters:**
- *Isolation Forest:* `n_estimators=150`, `max_samples=256` (the original paper's sub-sampling default ψ=256), `max_features=1.0`, `contamination='auto'` or set to your expected anomaly rate; score = average path length.
- *ECOD / COPOD:* none (parameter-free) — use as-is from PyOD.
- *Autoencoder:* symmetric MLP, bottleneck ≈ ¼–½ of input dim, ReLU, dropout 0.1–0.3, MSE reconstruction loss, early stopping; flag when reconstruction error exceeds a high percentile (e.g., 99th) of the normal-behaviour distribution.
- Library: **PyOD** (consistent API for all of the above).
**Sources:** Han, Hu, Huang, Jiang, Zhao, **ADBench**, NeurIPS 2022 (arXiv 2206.09426); Liu, Ting, Zhou, *Isolation Forest*, ICDM 2008; Li et al., **ECOD**, IEEE TKDE 2022; Li et al., **COPOD**, ICDM 2020; Schmidl et al., **TimeEval** ("Anomaly Detection in Time Series: A Comprehensive Evaluation"), VLDB 2022; Zhao et al., **PyOD**, JMLR 2019.

---

### 20.3 Layer 3 — Supervised tabular scorer (the workhorse)
**Candidates:** Logistic Regression, Random Forest, **XGBoost**, **LightGBM**, **CatBoost**, MLP, ResNet (tabular), **TabNet**, **FT-Transformer**, SAINT, TabPFN.
**Evidence — two landmark NeurIPS-2022 benchmarks + fraud-specific studies:**
- **Grinsztajn, Oyallon, Varoquaux (NeurIPS 2022; 45 datasets):** tree-based models (XGBoost, GBT, RF) remain **state-of-the-art on medium-sized tabular data (~10K samples)**, *even ignoring* their large speed advantage. **Hyperparameter tuning does not make neural nets competitive**, and the gap **persists on numerical-only features** (so it isn't just about categoricals). They trace it to NNs' inductive biases: they're hurt by uninformative features, are rotationally invariant (bad for tabular), and struggle with irregular/non-smooth target functions.
- **Shwartz-Ziv & Armon, *Tabular Data: Deep Learning is Not All You Need* (Information Fusion 2022):** across datasets, **XGBoost outperforms the deep tabular models**, and the best results come from **ensembling XGBoost with deep models** — but deep models alone do not win.
- **Fraud-specific head-to-heads:** on a 1.85M-record credit-card dataset, **CatBoost led (F1 0.9161) > XGBoost (0.8926) > LightGBM (0.8812)**; a real-time-oriented study found **LightGBM best on speed + large-data medians**, **CatBoost most stable under imbalance + high-cardinality categoricals**, **XGBoost robust but slightly less stable**. All three GBDTs beat DNNs at lower compute.
**Verdict:** **Gradient-boosted decision trees — and among them, LightGBM as the production default for the streaming scorer**, with **CatBoost as the strong alternative when high-cardinality categorical features dominate** (beneficiary IDs, merchant codes, branch/GL codes) and **XGBoost as the robust baseline**. **Benchmark all three on your data and pick per metric+latency** — but do *not* reach for deep tabular nets (TabNet/FT-Transformer) as the primary; the evidence says they won't beat tuned GBDTs here and cost far more.
**Why over alternatives:** GBDTs win the accuracy/robustness benchmarks on tabular fraud, train in minutes, serve in microseconds (ideal for the hot path), handle missing values and mixed types natively, and pair with **exact, fast TreeSHAP** explanations — which is decisive given your "contextual explanations" and regulatory requirements. LightGBM's histogram/leaf-wise growth makes it the fastest at your scale; CatBoost's ordered boosting + native categorical handling gives stability under imbalance and on ID-like features.
**Recommended starting parameters (then tune via time-aware CV + early stopping):**
- *LightGBM:* `objective=binary`, `metric=average_precision/auc`, `num_leaves=31→255`, `max_depth=-1` (or 6–12), `learning_rate=0.02–0.05`, `n_estimators=1000–3000` **with early stopping**, `feature_fraction=0.8`, `bagging_fraction=0.8`, `bagging_freq=1`, `min_child_samples=50–200`, and **`is_unbalance=true` or `scale_pos_weight=neg/pos`**.
- *XGBoost:* `tree_method=hist`, `max_depth=4–8`, `eta=0.01–0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `min_child_weight≥5`, `scale_pos_weight=neg/pos`, `eval_metric=aucpr`, early stopping.
- *CatBoost:* `depth=6–10`, `learning_rate=0.03–0.1`, `l2_leaf_reg=3–10`, `auto_class_weights=Balanced`, native `cat_features` for ID-like columns.
- **Imbalance handling around the model:** negative subsampling 1:3–1:10 (industry standard), class weights/focal loss, **then calibrate** (isotonic/Platt) so the 0–100 score is meaningful. Split train/test **by time**, never randomly.
**Sources:** Grinsztajn, Oyallon, Varoquaux, *Why do tree-based models still outperform deep learning on typical tabular data?*, NeurIPS 2022 D&B; Shwartz-Ziv & Armon, *Tabular Data: Deep Learning is Not All You Need*, Information Fusion 2022 (arXiv 2106.03253); Borisov et al., *Deep Neural Networks and Tabular Data: A Survey*, IEEE TNNLS 2022; *Comparative Study of CatBoost, XGBoost and LightGBM* (Preprints 2025, credit-card fraud); *Efficient ML Models for Real-Time Fraud Detection: CatBoost, XGBoost and LightGBM* (Research Square 2025); Chen & Guestrin, *XGBoost*, KDD 2016; Ke et al., *LightGBM*, NeurIPS 2017; Prokhorenkova et al., *CatBoost*, NeurIPS 2018.

---

### 20.4 Layer 4 — Sequence / multivariate time-series anomaly (low-and-slow & sessions)
**Candidates:** LSTM-autoencoder, **USAD**, **TranAD**, **Anomaly Transformer**, OmniAnomaly, MTAD-GAT, DeepLog/LogAnomaly (logs), **Deep Isolation Forest**, plus simple baselines (PCA, matrix-profile/one-liners, windowed Isolation Forest).
**Evidence — and this layer's evidence is mostly a *warning*:**
- **Wu & Keogh, *Current Time Series Anomaly Detection Benchmarks are Flawed and are Creating the Illusion of Progress* (IEEE TKDE 2020/2023):** the popular benchmarks (Yahoo, Numenta, NASA, SMD, SWaT, etc.) have **four serious flaws**, and **trivial "one-liners" (e.g., difference of consecutive points, moving average) achieve SOTA** on many of them — so much "progress" is **illusory**.
- **Kim et al., *Towards a Rigorous Evaluation of Time-Series Anomaly Detection* (AAAI 2022):** the widely-used **point-adjust (PA)** protocol **massively overestimates** performance — a **random-score baseline can beat reported SOTA under PA**. Absent proper baselines, you cannot tell if a method actually improved anything.
- ***Multivariate Time Series Anomaly Detection: Fancy Algorithms and Flawed Evaluation Methodology* (arXiv 2308.13068):** shows that under PA, **Anomaly Transformer is essentially just emitting anomalies at near-regular intervals** and still scores well — concluding PA "should no longer be used."
- **TimeEval (Schmidl et al., VLDB 2022; 71 algorithms × 967 datasets):** a **PCA baseline surprisingly outperforms many recent deep approaches**; performance is **highly dataset-dependent**.
**Verdict:** **Start with strong simple baselines (windowed PCA, windowed Isolation Forest, matrix-profile/one-liners, a small LSTM- or conv-autoencoder) and a rigorous, non-PA evaluation. Adopt TranAD (and/or USAD) only if it *demonstrably* beats those baselines on YOUR data under honest metrics.** TranAD remains the best deep candidate **because of its engineering properties, not benchmark hype** — it was explicitly designed for *scarce labels, high volatility, and ultra-low inference time* (it uses focus-score self-conditioning + adversarial training and is fast at inference), which matches production constraints; USAD (adversarial autoencoders) is a fast, stable second choice. **Do not present any of these as "SOTA"; present them as candidates that must earn their place.**
**Why this stance beats "just use the newest transformer":** the rigorous-evaluation literature is unambiguous that deep MTS-AD methods frequently **do not** beat simple baselines once PA is removed and benchmarks are de-flawed; deep models also cost far more to train/serve and are harder to explain. Choosing them by default would be buying complexity and cost for unproven gain — the opposite of "work smartly."
**Recommended evaluation + starting parameters:**
- **Evaluation:** report **range/affiliation-aware precision-recall** or **VUS-PR**, **never PA-only**; always include the simple baselines in the table; split by time.
- *Windowed IF / PCA baseline:* slide a window (e.g., 10–60 events or a session), featurize, score with Isolation Forest (params as §20.2) or PCA reconstruction error.
- *TranAD / USAD:* window length ≈ 10–100 steps, small latent dim, adversarial training as per paper; tune the anomaly-score threshold on a validation period; keep inference batched off the hot path (§18.2).
- *Log sequences:* DeepLog-style next-event prediction on parsed templates for privileged-session/DB log anomalies.
**Sources:** Wu & Keogh, IEEE TKDE 2020/2023 (arXiv 2009.13807); Kim, Choi, Choi, Lee, Yoon, AAAI 2022 (arXiv 2109.05257); *Fancy Algorithms and Flawed Evaluation Methodology* (arXiv 2308.13068); Schmidl, Wenig, Papenbrock, **TimeEval**, VLDB 2022; Audibert et al., **USAD**, KDD 2020; Tuli, Casale, Jennings, **TranAD**, VLDB 2022 (arXiv 2201.07284); Xu et al., **Anomaly Transformer**, ICLR 2022 (arXiv 2110.02642); Xu et al., **Deep Isolation Forest**, IEEE TKDE 2023.

---

### 20.5 Layer 5 — Graph / relational (collusion, mule chains, maker-checker rings)
**Candidates:** GCN, GIN, **GraphSAGE**, GAT, Graph Transformer; specialized fraud GNNs — **CARE-GNN**, **PC-GNN**, **BWGNN**, GAT-sep, H2-FDetector, GAGA; heterogeneous GNNs (RGCN, HGT, GoSage); and **tree-ensembles-with-neighborhood-aggregation (XGB-Graph / RF-Graph)**.
**Evidence — GADBench (Tang et al., NeurIPS 2023; ~29 models × 10 real datasets up to ~6M nodes):**
- **The headline, and it's counterintuitive: tree ensembles with simple neighborhood aggregation (XGB-Graph) OUTPERFORM the best specialized GNNs.** XGB-Graph beat the best GNN (BWGNN) by **+2.0% AUROC, +12.9% AUPRC, +9.8% Rec@K** (fully-supervised); RF-Graph beat the best GNN (GHRN) by **+2.8% AUROC, +8.0% AUPRC** (semi-supervised). Tree ensembles were also **more efficient** (less time/memory) and **scaled better** to large graphs.
- **Standard GNNs (GCN, GIN) often do no better than an MLP** that ignores graph structure — because fraud graphs exhibit **heterophily/camouflage** (fraudsters deliberately connect to benign nodes and mimic their features — exactly your doc's "engineered to look normal"). **GraphSAGE is the standout exception** among standard GNNs (**+10.4% AUPRC** when tuned, competitive with specialized GNNs) and is **inductive** (handles new nodes).
- **Specialized GNNs** (CARE-GNN's RL neighbor selector, PC-GNN's label-balanced sampler, BWGNN's spectral bandpass for the "right-shift" phenomenon) are built to defeat camouflage/heterophily/imbalance and **beat standard GNNs** — but still **lose to XGB-Graph** in the benchmark.
**Verdict:** **Start the graph layer with XGB-Graph / RF-Graph (k-hop neighborhood aggregation features → your existing GBDT)** — best benchmark performance, reuses Layer-3 infrastructure, efficient at millions of nodes. **Add GraphSAGE when you need inductive representation learning** for streaming new nodes/edges. **Bring in camouflage-resistant specialized GNNs (CARE-GNN / PC-GNN / BWGNN) specifically for the hard collusion/heterophily cases** where XGB-Graph plateaus. Use heterogeneous GNNs (HGT/GoSage) only if your entity graph is richly multi-typed and the simpler approaches are exhausted.
**Why over alternatives:** GADBench shows end-to-end GNNs are **not the automatic best choice** for supervised graph fraud and are heavier and harder to scale/explain; "graph features + GBDT" captures most of the relational signal at a fraction of the cost — the smart enterprise default. GraphSAGE earns inclusion because inductive scoring of new nodes is operationally essential. Specialized GNNs earn inclusion because **camouflage is precisely the collusion problem** your doc centers on, and they are purpose-built for it.
**Recommended starting parameters:**
- *XGB-Graph / RF-Graph:* compute per-node **k-hop aggregates** (mean/sum/max of neighbor features, degree, centrality, shared-attribute counts) for k=1–2, then feed GBDT (params as §20.3). GADBench confirms going from 0→2 aggregation hops improves results.
- *GraphSAGE:* 2 layers, hidden dim 128–256, **mean** aggregator, neighbor sample sizes ≈ [25, 10], dropout 0.5, lr 0.01, Adam; train with class weighting / focal loss for imbalance.
- *CARE-GNN / PC-GNN / BWGNN:* use the authors' reference configs as starting points; they require tuning (GADBench notes specialized GNNs need it). Libraries: **PyTorch Geometric / DGL**; **PyGOD** for graph outlier methods.
- **Graph construction:** entities (employees, accounts, beneficiaries, devices, vendors) as nodes; transactions/access/shared-attributes as typed edges; refresh incrementally (§18.2). Use **GNNExplainer**-style attribution for regulator-facing reasons.
**Sources:** Tang, Hua, Gao, Zhao, Li, **GADBench**, NeurIPS 2023 (arXiv 2306.12251); Hamilton, Ying, Leskovec, **GraphSAGE**, NeurIPS 2017; Veličković et al., **GAT**, ICLR 2018; Dou et al., **CARE-GNN**, CIKM 2020; Liu et al., **PC-GNN**, WWW 2021; Tang et al., **BWGNN** (*Rethinking GNNs for Anomaly Detection*), ICML 2022; Ghosh et al., **GoSage**, ACM ICAIF 2023; Johannessen & Jullum, *Finding money launderers using heterogeneous GNNs* (DNB), 2024; **safe-graph/graph-fraud-detection-papers** (curated repo); Liu et al., **PyGOD**, 2022.

---

### 20.6 Cross-cutting — Explainability (the "contextual explanations" requirement)
**Candidates:** **SHAP** (TreeSHAP / KernelSHAP), **LIME**, **Anchors**, **counterfactuals (DiCE / Alibi)**, attention (LAXCAT), rule provenance.
**Evidence:** Comparative XAI-for-fraud studies find **SHAP gives more consistent global+local attributions than LIME** (LIME's perturbation-based local surrogates are less stable); **counterfactual explanations are increasingly favored by regulators** because they give *actionable recourse* ("had the export volume been below X, it would not have flagged") and match how analysts reason; a 2026 systematic review flags an over-reliance "monoculture" on SHAP/LIME and recommends counterfactual/causal methods that **resist forged correlations**. **Critical caveat (also a security issue, §19.2): SHAP and LIME explanations can be adversarially manipulated** (Slack et al., AIES 2020) — so explanations must be **defense-in-depth**, cross-checked against rules and raw evidence.
**Verdict:** **TreeSHAP for live reason codes** (exact and fast on your GBDTs — ideal for the hot path) **+ counterfactuals (DiCE/Alibi) for investigator-facing actionable recourse + rule provenance for the deterministic layer + attention (LAXCAT) for session explanations.** Reserve **SHAP interaction values for offline/regulatory documentation** (≈ quadratic in features — too heavy for real-time).
**Why over alternatives:** TreeSHAP is exact for trees (no sampling noise like KernelSHAP/LIME), fast enough for inline use, and game-theoretically grounded — the right primary for a regulated, real-time fraud system. Counterfactuals add the recourse regulators want. Relying on a single post-hoc method is unsafe given the manipulation results, hence the layered approach.
**Sources:** Lundberg & Lee, **SHAP**, NeurIPS 2017; Lundberg et al., **TreeSHAP**, Nature MI 2020; Ribeiro et al., **LIME**, KDD 2016; Mothilal et al., **DiCE** (counterfactuals), ACM FAT* 2020; Slack et al., *Fooling LIME and SHAP*, AIES 2020 (arXiv 1911.02508); *Methodological challenges in explainable AI for fraud detection: a systematic review*, AI Review 2026.

---

### 20.7 Cross-cutting — Risk fusion & calibration (Layer 6)
**Candidates:** weighted average of layer scores; **stacked meta-learner** (logistic regression or a shallow GBDT over the layer outputs + rule flags); rank-based fusion.
**Evidence/Verdict:** use a **transparent stacked meta-model** (logistic regression or shallow LightGBM over the per-layer scores and rule hits) so the *final* decision is itself explainable, then **calibrate** (isotonic regression) so the 0–100 score maps to real fraud probability. Calibration matters operationally because your alert threshold is set against **analyst capacity** — an uncalibrated score makes threshold-setting guesswork.
**Why:** stacking consistently beats naive averaging when base learners have different strengths (which yours do, by construction: rules/unsupervised/supervised/sequence/graph), while a transparent meta-learner preserves auditability. **Sources:** Wolpert, *Stacked Generalization*, 1992; Shwartz-Ziv & Armon 2022 (ensembling deep+GBDT wins); standard calibration practice (Platt 1999; isotonic regression).

---

### 20.8 One-screen decision summary

| Layer | Use this (default) | Strong alternatives / when | Avoid as primary | Anchor benchmark |
|---|---|---|---|---|
| L1 Rules | Deterministic BRE (SoD/toxic-combo) | Flink-CEP for streaming rules | Pure-rules-only system | Vendor + event-driven pipeline studies |
| L2 Unsupervised | **Isolation Forest** (+ ECOD/COPOD; AE for explanations) | Autoencoder for non-linear "normal" | DeepSVDD/DAGMM (cost without reliable gain) | **ADBench** (NeurIPS'22) |
| L3 Supervised | **LightGBM** (default) | **CatBoost** (high-cardinality/imbalance), XGBoost (robust) | TabNet/FT-Transformer (won't beat GBDT here) | **Grinsztajn**, Shwartz-Ziv (NeurIPS/IF'22) |
| L4 Sequence | **Simple baselines first** (windowed PCA/IF, small AE); **TranAD/USAD only if they beat them** | TranAD for low-latency deep; DeepLog for logs | Any deep model chosen on PA-inflated scores | **Wu&Keogh**, **Kim'22**, **TimeEval** |
| L5 Graph | **XGB-Graph / RF-Graph** (graph-features + GBDT) | **GraphSAGE** (inductive); CARE-GNN/PC-GNN/BWGNN (camouflage) | Vanilla GCN/GIN (≈ MLP under heterophily) | **GADBench** (NeurIPS'23) |
| Explain | **TreeSHAP** + counterfactuals + rule provenance | LAXCAT for session attention | SHAP interaction values in real-time (too slow) | XAI-fraud reviews; Slack'20 |
| L6 Fusion | **Stacked meta-learner + isotonic calibration** | Weighted average (simplest) | Uncalibrated raw scores | Stacking + calibration literature |

**The through-line:** every rigorous, independent benchmark — ADBench, Grinsztajn, TimeEval, GADBench — points the same way: **tree-based and simple methods win or tie on accuracy while crushing deep models on cost, latency, and explainability** for this class of problem. Lead with them; add deep sequence/graph models surgically, only where they *prove* they earn their keep on your data under honest evaluation. That is both the best-performing and the most defensible (and most "enterprise-smart") path.


---
---

# ADDENDUM II (appended on request)
### Parts 21–26: Dataset Creation · Training · Model Storage · The Application (RBAC/routing/versions/UI/samples) · TEE-Attested LLM Gateway · AWS Pilot Deployment

> **Deployment framing (confirmed):** **On-prem is the production target** — Parts 8–9 remain the production reference. **AWS is the "for-now" buildable pilot** (Part 26). The architecture is deliberately all-open-source/self-hostable, so the AWS pilot migrates cleanly back to on-prem (managed AWS services are conveniences, not lock-in). **LLM data policy (confirmed):** the external TEE LLM may receive full context **but with PII hashed/tokenized before egress**, with TEE attestation as the trust anchor (Part 25). *(No real `NEAR_AI_API_KEY` is embedded anywhere — it is injected at runtime from a secrets manager.)*

---

## PART 21 — HOW WE CREATE THE DATASET

There are **two data sources**, used at different stages: **(A) synthetic** (carries cold start and the red-team library) and **(B) real telemetry** (the production signal, once wired up). Both land in the **same unified event schema** (Part 5.1).

### 21.1 The agent-based synthetic data simulator (the core mechanism)
Because no real insider-banking dataset exists publicly and labels are scarce, we **manufacture** behaviourally-realistic, labelled data that embeds the **exact typologies from your reference document**. Agent-based simulation (not naive GANs) is used because it preserves the temporal/velocity/multi-account structure that behavioural fraud depends on.

**Simulator components**
1. **Population model** — generate N employees with `role, department, branch, tenure, manager, peer_group, privileged_flag`, sampled to mirror your org shape (e.g., 50k staff, a few hundred privileged).
2. **Normal-behaviour model** — per-role activity generators with realistic **diurnal/weekly rhythms**: tellers post cash in branch hours; DBAs run batch jobs at night; ops makers/checkers pair on payments; analysts disposition alerts. Emits transaction, access, data-layer, and change events with realistic volumes and noise.
3. **Fraud-scenario injectors** — one module per typology, each producing a labelled trace embedded in normal traffic:
   - *Beneficiary-then-approve* (new payee → high-value payment by same maker/checker)
   - *Dormant-account takeover* (reactivation → silent channel enrollment → drain)
   - *SWIFT-without-CBS* (instrument message with **no matching CBS posting** — the PNB mechanism)
   - *Suspense/nostro lapping* (aging items; same actor posts + reconciles)
   - *Privilege self-grant* (short-lived entitlement timed around a fraudulent approval)
   - *Bulk exfiltration before resignation* (download spike in the notice-period window)
   - *Maker-checker collusion ring* (a recurring colluding pair/cluster — feeds the graph layer)
   - *Rogue-trader pattern* (no-leave + late/cancelled-rebooked trades)
4. **Ground-truth labels** — every event tagged `is_fraud`, `scenario_id`, `actor_id`, `ring_id` (for collusion).

**Implementation:** Python with **SimPy** or **Mesa** (agent-based modelling), referencing **PaySim/MoMTSim** for transaction realism. Output to **Parquet** (and streamed into Kafka for end-to-end pipeline testing). **Scale knobs:** number of agents, time span (e.g., 18 months to match CERT), and a **realistic fraud rate** (keep it rare — ~0.1–1% of actors, far fewer events — so models learn the true imbalance, not a balanced toy).

### 21.2 Generative augmentation (rare-class only)
For the **supervised** layer, oversample the minority class with **CTGAN / TVAE / diffusion (SDV library)** — **but only in feature space**, and anchored to real distributions, because (as the 2026 benchmark showed) naive tabular generators break behavioural signals. Behavioural realism always comes from the agent simulator; generative models only pad the tabular feature distribution.

### 21.3 Real telemetry & labelling
- **Real events** ingest through the unified event model from CBS/SWIFT/IAM/PAM/DB-audit/IGA/HR (Part 5.2).
- **Labels** come from four sources (Part 5.4): known historical cases (gold), Layer-1 rule hits (weak labels), synthetic ground truth, and — the compounding engine — **EDD feedback**. Use **PU-learning / semi-supervised** methods to exploit the unlabelled majority.

### 21.4 Splits & leakage avoidance (do this right or metrics lie)
- **Temporal split** — train on the past, validate/test on the future (fraud detection is a forecasting problem). Never random-split.
- **Entity-disjoint** validation where needed (don't let the same employee leak across splits).
- **Remove leaky features** (e.g., PaySim's balance columns; any field that encodes the label).

### 21.5 Dataset storage & versioning
- **Raw events:** ClickHouse (queryable history) **+** object store (**S3** on AWS / **MinIO** on-prem) as **partitioned Parquet** (by date/source).
- **Curated training sets:** versioned in the object store, tracked with **DVC** or **MLflow data artifacts**; each set carries a **content hash**.
- **Feature definitions:** **Feast** offline store (the *same* definitions serve online — no train/serve skew).
- **Lineage:** every model records the **dataset hash + feature-set version** it was trained on (audit + reproducibility).

---

## PART 22 — HOW WE TRAIN THE MODELS

### 22.1 Orchestration
Training pipelines run as **Airflow / Dagster** DAGs, parameterized by layer. Each run: pull data (ClickHouse/Feast/object store) → build features → train → validate → calibrate → register (MLflow) → (optionally) shadow-deploy.

### 22.2 Per-layer training procedure
- **L2 Unsupervised (no labels):** fit **Isolation Forest / ECOD / autoencoder** on a window of **normal** behaviour, computed **per-entity and per-peer-group** with time decay. Persist baselines + thresholds (e.g., 99th-percentile reconstruction error). Refresh on a schedule; guard against low-and-slow poisoning with peer-anchoring + change-point checks.
- **L3 Supervised (GBDT):** feature pipeline → **time-aware cross-validation** with **early stopping** → class weighting / `scale_pos_weight` + 1:3–1:10 negative subsampling → **isotonic calibration** so the 0–100 score is a real probability → evaluate on **AUPRC / Rec@K** (not accuracy) → register. Default **LightGBM**; benchmark **CatBoost** (categorical-heavy) and **XGBoost** (robust) per §20.3.
- **L4 Sequence:** build windowed features → train the **simple baselines first** (windowed PCA/IF, small AE), then optionally **TranAD/USAD** → evaluate with **range/affiliation-aware metrics, never point-adjust** (§20.4) → keep the deep model only if it beats baselines.
- **L5 Graph:** construct/refresh the entity graph → train **XGB-Graph** (k-hop aggregation features + GBDT) and/or **GraphSAGE** → evaluate (AUPRC/Rec@K) → register (§20.5).
- **L6 Fusion:** train a **transparent stacked meta-learner** (logistic / shallow LightGBM) over the per-layer scores + rule flags → **calibrate**.

### 22.3 The feedback-loop retraining (what makes it improve)
EDD disposition → **labelled store** → **active learning** (prioritize uncertain/high-value cases) → scheduled retrain → **shadow mode** → **champion/challenger** → **canary** rollout with auto-rollback on metric regression. Drift monitors (Evidently/PSI) trigger off-cycle retrains.

### 22.4 Reproducibility & governance
Fixed seeds; **dataset + feature hashes** recorded; full **MLflow** tracking (params, metrics, artifacts); an auto-generated **model card**; and a required **independent validation sign-off** before Production promotion (model-risk-management requirement).

### 22.5 Compute
**Trees train on CPU** in minutes. **Sequence/graph nets train on GPU.** On the AWS pilot: a **GPU instance (g5/p4d)** for periodic training; **CPU instances** for serving. On-prem: a small GPU pool for training, CPU for inference.

---

## PART 23 — HOW MODEL FILES ARE STORED

### 23.1 Formats
- **Trees:** export to **ONNX** (for low-latency serving) **and** keep the native booster (`.txt`/`.cbm`/`joblib`) for warm-start retraining.
- **Nets (L4/L5):** **ONNX** for serving + **PyTorch checkpoint** for retraining.
- **Preprocessors / feature transformers / calibrators:** versioned **together with** the model (a model is never just the estimator — it's the whole transform chain).

### 23.2 Registry & layout
- **MLflow Model Registry** with stages **Staging → Production → Archived**; artifacts stored in the object store: `s3://frauд-models/{layer}/{model}/{version}/` (AWS) or the MinIO equivalent (on-prem).
- Each version records: **dataset hash, params, metrics, training code commit, approver, and a cryptographic signature**.

### 23.3 Storage security
- **Encrypted at rest** (S3 **SSE-KMS** / MinIO encryption); **versioned + object-lock** (immutable) buckets; **least-privilege** access (IAM/RBAC); **model signing** with signature **verified on load** (supply-chain integrity, per Part 19.4). Lifecycle rules archive old versions.

### 23.4 Serving load path
The serving runtime (**ONNX Runtime / Triton**) pulls the **Production** artifact from the registry, **verifies its signature**, and hot-swaps via canary. Every served score records the **model version** used (reproducibility + audit + natural-justice).

---

## PART 24 — THE APPLICATION (RBAC · API routing · platform versions · UI/screens · sample payloads)

### 24.1 RBAC — roles and permission matrix
Authentication via **OIDC/OAuth2** (Keycloak) issuing short-lived **JWTs**; every API call is RBAC-checked; **PII re-identification is a separate, audited permission** (most users see tokenized PII; only specific roles can unmask).

| Capability → / Role ↓ | View alerts | Triage / assign | Disposition (fraud/FP) | Request block | Unmask PII | Tune rules/thresholds | Train/deploy models | View audit log | Admin (users/infra) |
|---|---|---|---|---|---|---|---|---|---|
| **Analyst (L1 investigator)** | ✅ (assigned) | ✅ | ✅ | ✅ (request) | ⚠️ case-scoped, logged | ❌ | ❌ | ❌ | ❌ |
| **Senior Investigator** | ✅ (all) | ✅ | ✅ | ✅ | ✅ logged | ❌ | ❌ | view own | ❌ |
| **Team Lead / MLRO** | ✅ | ✅ | ✅ (override) | ✅ approve | ✅ logged | ⚠️ propose | ❌ | ✅ | ❌ |
| **Compliance Officer** | ✅ | ❌ | ❌ | ❌ | ✅ logged | ✅ (change-controlled) | ❌ | ✅ | ❌ |
| **Auditor** | ✅ read-only | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ full | ❌ |
| **Model Engineer / Data Scientist** | ⚠️ de-identified only | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (with sign-off) | view own | ❌ |
| **Platform Admin** | ❌ (no case data) | ❌ | ❌ | ❌ | ❌ | ❌ | ⚠️ deploy infra | ✅ | ✅ |
| **Service accounts** | scoped tokens | — | — | — | ❌ | ❌ | ❌ | write-only | ❌ |

**Key SoD rule (Part 19.6):** the person who **deploys models** (Model Engineer) cannot **label data** or **close their own alerts**; the person who **investigates** cannot **tune the rules** that generate their alerts unchecked. This prevents the anti-fraud system from being quietly turned against the bank or an individual.

### 24.2 API routing (REST, OpenAPI-style)
Base path `/api/v1`. All routes require a valid JWT; the **RBAC** column shows the minimum role. JSON over HTTPS (mTLS internally).

| Method & path | Purpose | RBAC |
|---|---|---|
| `POST /auth/login`, `POST /auth/refresh` | OIDC token exchange / refresh | public |
| `GET /alerts?status=&risk_gte=&assignee=` | Ranked alert queue (paginated) | Analyst |
| `GET /alerts/{id}` | Full alert (score, reason codes, contributing layers) | Analyst |
| `POST /alerts/{id}/assign` | Assign/claim an alert | Analyst |
| `POST /alerts/{id}/disposition` | Submit EDD outcome (`fraud`/`false_positive`/`inconclusive`) → **label** | Analyst |
| `POST /alerts/{id}/block-request` | Raise a block request (human action, never auto) | Analyst→Lead approves |
| `GET /entities/{id}` | Entity-360 (actor profile + risk) | Analyst |
| `GET /entities/{id}/timeline` | Unified transaction+access+data+change timeline | Analyst |
| `GET /entities/{id}/graph` | Relationship/collusion subgraph | Analyst |
| `GET /entities/{id}/peers` | Peer-group comparison on flagged dimension | Analyst |
| `GET /explanations/{alert_id}` | SHAP reason codes + rule provenance + attention | Analyst |
| `POST /narratives/{alert_id}` | **TEE LLM** narrative/summary (Part 25) | Analyst |
| `POST /entities/{id}/unmask` | Re-identify tokenized PII (audited) | Senior+ |
| `GET/POST/PUT /rules` | Rule/threshold CRUD (change-controlled) | Compliance |
| `GET /models`, `POST /models/{id}/promote` | Registry view / promotion | Model Eng (deploy: + sign-off) |
| `GET /drift`, `GET /metrics/model` | Drift & model-quality dashboards | Model Eng |
| `POST /feedback` | Active-learning label submission | Analyst |
| `GET /reports/fmr`, `GET /reports/crilc` | Regulatory export (FMR/CRILC) | Compliance |
| `GET /audit?actor=&entity=&from=&to=` | Immutable audit trail (incl. who-viewed-whom) | Auditor |
| `GET /admin/users`, `POST /admin/users` | User/role management | Platform Admin |
| `GET /health`, `GET /metrics` | Liveness + Prometheus metrics | service |

### 24.3 Platform / tech-stack versions (reference pins — verify latest patch before locking)
| Component | Version (pin) | Role |
|---|---|---|
| Apache Kafka | 3.8.x (or 4.0) | event ingestion |
| Apache Flink | 1.20.x | stateful streaming/CEP |
| ClickHouse | 25.x | analytics/investigation store |
| Redis | 7.4.x | online feature store/cache |
| Feast | 0.40.x | feature store (train/serve parity) |
| PostgreSQL | 17.x | app metadata (cases, users) |
| Python | 3.12.x | ML + services |
| LightGBM / XGBoost / CatBoost | 4.5.x / 2.1.x / 1.2.x | L3/L5 GBDT |
| PyTorch / PyTorch-Geometric | 2.5.x / 2.6.x | L4/L5 deep models |
| PyOD / scikit-learn | 2.0.x / 1.6.x | L2 anomaly / utilities |
| ONNX Runtime / Triton | 1.20.x / 25.x | model serving |
| FastAPI / Uvicorn | 0.115.x / 0.32.x | API layer |
| React / TypeScript / Node | 19.x / 5.6.x / 22.x | dashboard frontend |
| MLflow | 2.18.x (or 3.x) | model registry/tracking |
| Airflow (or Dagster) | 2.10.x | orchestration |
| Drools (or OPA) | 8.x | rules engine |
| Keycloak | 25.x | OIDC/OAuth2 auth |
| Evidently | 0.4.x | drift monitoring |
| Prometheus / Grafana | 3.x / 11.x | metrics/observability |
| Docker / Kubernetes | 27.x / 1.31.x | runtime/orchestration |
| OpenAI Python SDK | 1.5x.x | LLM gateway client (NEAR AI/Groq) |
| Terraform | 1.9.x | IaC (AWS + on-prem targets) |

*(Pin exact patch versions in your lockfiles; track CVEs per Part 19.5. Treat this as a starting BOM, not gospel.)*

### 24.4 UI / screens — what each persona sees
1. **Login / SSO** — OIDC redirect; MFA; session controls.
2. **Triage queue (Analyst home)** — alerts ranked by fused risk × exposure × confidence; filters (status, risk, assignee, type); **SLA/TAT timer** (RBI ≤30-day); one-click claim. Deduped per entity.
3. **Alert / Case detail** — the workhorse screen:
   - Header: risk score (0–100), severity×confidence, status, SLA timer.
   - **Entity-360 + Timeline:** the actor's transactions, access, data-layer, and change events on one timeline.
   - **Explanation panel:** SHAP reason codes + **rule provenance** + sequence attention + the **AI-generated narrative** (clearly labelled, Part 25).
   - **Graph view:** beneficiary/collusion/shared-identity subgraph.
   - **Peer comparison:** this actor vs peer group on the flagged dimension.
   - **EDD checklist + Actions:** disposition, request-block, notes, unmask (if permitted) — every action audited.
4. **Case management** — assignment, status, linked alerts, notes, history.
5. **Compliance view** — EWS/RFA dashboard; threshold/rule change-control; **CRILC/FMR export**.
6. **Auditor view** — read-only immutable audit trail, including **who viewed which employee** and who closed what.
7. **Model engineer view** — registry (champion/challenger), **drift dashboards**, model-quality metrics — on **de-identified** data only.
8. **Admin view** — users/roles, rule deployment, system health (Grafana embed).

### 24.5 Sample payloads (event · alert · API · worked burst)

**(a) Sample unified event (input to the pipeline):**
```json
{
  "event_id": "evt_8f2a1c90",
  "ts": "2026-06-30T02:14:07Z",
  "actor": { "employee_id": "EMP-7f3a", "role": "ops_maker", "dept": "trade_finance",
             "branch": "BR-219", "tenure_days": 2840, "peer_group": "PG-ops-tf",
             "privileged_flag": false, "leaver_flag": false },
  "action": { "verb": "create_beneficiary", "channel": "cbs", "maker_checker": "maker" },
  "object": { "beneficiary_id": "BEN-9b1c", "account_id": "ACCT-4d22", "amount": null, "currency": "INR" },
  "context": { "src_ip": "10.20.4.31", "device": "WS-114", "geo": "Mumbai",
               "session_id": "sess_55e1", "layer": "application", "is_off_hours": true }
}
```

**(b) Sample alert (output of L6 fusion):**
```json
{
  "alert_id": "alr_3d7e22",
  "entity_id": "EMP-7f3a",
  "risk_score": 87,
  "severity": "high",
  "confidence": 0.82,
  "status": "open",
  "created_ts": "2026-06-30T02:41:55Z",
  "contributing_layers": ["L1_rules", "L2_unsupervised", "L3_gbdt", "L5_graph"],
  "reason_codes": [
    { "source": "rule",  "code": "NEW_BENEFICIARY_THEN_HIGHVALUE", "detail": "new payee BEN-9b1c paid INR 48,00,000 within 27 min" },
    { "source": "rule",  "code": "OFF_HOURS_ACTIVITY", "detail": "02:14 IST, outside actor & peer baseline" },
    { "source": "shap",  "feature": "new_beneficiary_to_payment_latency_min", "contribution": 0.31 },
    { "source": "shap",  "feature": "maker_checker_pair_frequency_30d", "contribution": 0.22 },
    { "source": "graph", "detail": "maker EMP-7f3a + checker EMP-1a09 recur as an isolated pair (ring_id RNG-12)" }
  ],
  "exposure_inr": 4800000,
  "sla_due_ts": "2026-07-30T02:41:55Z",
  "pii_tokenized": true
}
```

**(c) Sample API request/response:**
```http
POST /api/v1/alerts/alr_3d7e22/disposition
Authorization: Bearer <jwt>
Content-Type: application/json

{ "outcome": "fraud", "notes": "Confirmed shell beneficiary; maker-checker collusion. Escalating to Vigilance.", "evidence_ids": ["evt_8f2a1c90","evt_8f2a1d04"] }
```
```json
// 200 OK
{ "alert_id": "alr_3d7e22", "status": "confirmed_fraud", "label_written": true,
  "feedback_queued_for_retraining": true, "audit_id": "aud_99f0c1" }
```

**(d) Worked synthetic "burst" → alert (end-to-end):**
| t | Event (synthetic) | Layer reaction |
|---|---|---|
| 02:14:07 | `create_beneficiary` BEN-9b1c by maker EMP-7f3a, **off-hours** | L1: OFF_HOURS flag; L2: deviates from EMP-7f3a + peer baseline |
| 02:33:10 | `approve_payment` INR 48,00,000 to BEN-9b1c, checker EMP-1a09 | L1: **NEW_BENEFICIARY_THEN_HIGHVALUE** fires; L3 GBDT score ↑ (latency + amount z-score) |
| 02:33:11 | Graph update: maker EMP-7f3a + checker EMP-1a09 edge | L5: recurring isolated maker-checker pair → ring candidate RNG-12 |
| 02:41:55 | — | **L6 fusion → risk 87 (high)**; reason codes assembled; alert `alr_3d7e22` emitted |
| 02:41:56 | — | LLM narrative generated (Part 25); alert lands top of Analyst queue with SLA timer |

This burst is exactly what the **synthetic simulator (Part 21)** emits as a labelled positive, and what the **demo/pilot** replays to show the system working end-to-end.

---

## PART 25 — TEE-ATTESTED NARRATIVE LLM GATEWAY (NEAR AI Cloud · gpt-oss-120b)

### 25.1 Purpose and placement (what the LLM does — and does NOT do)
The LLM is a **narrative gateway**, not a detector. It turns a **scored, evidenced alert** into an **investigator-readable narrative and case summary** ("what happened, why it flagged, what to check"), and can draft the SAR/FMR narrative. **It never makes the fraud decision** — the score comes from L1–L6; the LLM only *explains*. It sits **after L6 fusion** (Part 18) and feeds the **dashboard explanation panel** (Parts 11, 24) via `POST /narratives/{alert_id}`. This keeps the detection auditable and deterministic while adding a genuinely useful language layer.

### 25.2 Why a TEE (this is what makes an external LLM defensible for a bank)
Normally, sending insider-fraud context to an external LLM is forbidden (residency + privacy). A **Trusted Execution Environment** removes that objection:
- **Intel TDX (CPU) + NVIDIA H200 (GPU) confidential compute** — data is **encrypted in use** (in memory, in VRAM, across the PCIe bus); even the **infrastructure operator cannot read it**.
- **TLS terminates *inside* the enclave** (NEAR AI gateway mode: `cloud-api.near.ai` runs in its *own* TEE, then forwards to the model TEE) — prompts are never plaintext outside hardware.
- **Per-request cryptographic attestation** — each TEE emits a signed quote (Intel TDX + NVIDIA dual attestation) proving a genuine, untampered enclave running the expected model. The gateway **verifies and stores** the attestation report for audit.
This aligns with the system's "zero-trust, prove-it" philosophy and is the privacy-preserving way to add the LLM angle even before on-prem migration.

### 25.3 PII handling — hashed/tokenized before egress (confirmed policy)
Even with a TEE, **defense-in-depth**: a **tokenization layer** runs **before** any call leaves the perimeter.
- PII fields (names, account numbers, PANs, addresses, phones) → **deterministic keyed tokens** via **HMAC-SHA256(secret_key, value)** truncated to a readable token (`EMP-7f3a`, `ACCT-4d22`, `BEN-9b1c`).
- The **token↔real mapping lives in a local re-identification vault** (never sent out); the **dashboard de-tokenizes on display** for authorized users (Part 24.1 unmask permission).
- Result: the LLM sees **behaviour + structure + tokens**, never raw PII — and the TEE guarantees even that is invisible to the provider.

### 25.4 Architecture, failover, and audit columns
**Primary → secondary → deterministic fallback (UI never breaks):**
1. **NEAR AI Cloud** (`https://cloud-api.near.ai/v1`, model `openai/gpt-oss-120b`, gateway mode, attestation verified).
2. On error/timeout → **Groq** (`https://api.groq.com/openai/v1`, same `openai/gpt-oss-120b`) — fast, OpenAI-compatible. *(Note: Groq is **not** a TEE path, so the audit memo records `tee_attested=false` for these — a deliberate, logged degradation; PII is still tokenized.)*
3. On both failing → **deterministic Jinja template** that renders a structured narrative from the reason codes — **no LLM, always works.**

Every generated narrative writes an **audit memo** with: `provider` (`near_ai`/`groq`/`template`), `tee_attested` (bool), `attestation_id` (when applicable), `model`, `prompt_hash`, `timestamp`. This makes the provenance of every AI-written word auditable — essential in a regulated setting.

### 25.5 Integration sketch (Python, OpenAI SDK)
```python
import os, time, hmac, hashlib
from openai import OpenAI
from jinja2 import Template

def tok(v, k=os.environ["PII_HMAC_KEY"].encode()):
    return hmac.new(k, str(v).encode(), hashlib.sha256).hexdigest()[:8]

NEAR = OpenAI(base_url="https://cloud-api.near.ai/v1", api_key=os.environ["NEAR_AI_API_KEY"])
GROQ = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"])
MODEL = "openai/gpt-oss-120b"

SYS = ("Reasoning: medium\n"
       "You are a bank fraud-investigation assistant. Write a concise, factual narrative of why this "
       "alert fired and what the investigator should verify. Use ONLY the provided evidence; never invent "
       "facts, names, or numbers. Identifiers are tokens (e.g., EMP-7f3a); do not try to de-anonymize them.")

def narrate(alert_ctx: dict) -> dict:
    # alert_ctx is already PII-tokenized upstream
    user = f"Alert evidence (tokenized):\n{alert_ctx}"
    for provider, client, tee in (("near_ai", NEAR, True), ("groq", GROQ, False)):
        try:
            r = client.chat.completions.create(
                model=MODEL, temperature=0.2, max_tokens=500,
                messages=[{"role":"system","content":SYS},{"role":"user","content":user}])
            att = verify_and_store_attestation(provider)  # NEAR AI: fetch+verify TEE quote; Groq: None
            return {"narrative": r.choices[0].message.content, "provider": provider,
                    "tee_attested": tee and att is not None, "attestation_id": att,
                    "model": MODEL, "ts": time.time()}
        except Exception:
            continue
    # deterministic fallback — UI never breaks
    tmpl = Template("Alert {{a.alert_id}} (risk {{a.risk_score}}): "
                    "{% for r in a.reason_codes %}{{r.detail or r.code}}. {% endfor %}"
                    "Recommend verifying beneficiary, maker-checker independence, and off-hours justification.")
    return {"narrative": tmpl.render(a=alert_ctx), "provider": "template",
            "tee_attested": False, "attestation_id": None, "model": None, "ts": time.time()}
```

### 25.6 Sample request/response
```json
// POST /api/v1/narratives/alr_3d7e22  → response
{
  "narrative": "Maker EMP-7f3a created a new beneficiary BEN-9b1c at 02:14 IST (outside their own and their peer group's normal hours) and a payment of INR 48,00,000 was approved to that payee 27 minutes later by checker EMP-1a09. The same maker-checker pair recurs as an isolated cluster (ring RNG-12). Recommended checks: verify BEN-9b1c is a legitimate, independently-onboarded payee; confirm maker-checker independence; obtain justification for the off-hours activity; review prior payments to BEN-9b1c.",
  "provider": "near_ai",
  "tee_attested": true,
  "attestation_id": "att_5c1f9a",
  "model": "openai/gpt-oss-120b"
}
```

### 25.7 Guardrails
- Output is **advisory and labelled "AI-generated"**; it never triggers an action.
- The prompt **forbids fabrication and de-anonymization**; outputs are **grounded** against the structured reason codes (reject/flag if the narrative introduces facts not in evidence).
- Rate-limited; `gpt-oss` reasoning effort set to **medium** (balance latency/quality); temperature low (0.2) for faithful, non-creative summaries.

---

## PART 26 — AWS PILOT DEPLOYMENT (the "for-now" build) + MIGRATION TO ON-PREM

> On-prem (Parts 8–9) remains the production target. This is the **buildable pilot** on AWS, in the **Mumbai region (`ap-south-1`)** for data residency. Everything maps 1:1 back to on-prem because the stack is open-source.

### 26.1 AWS component mapping (`ap-south-1`)
| Component | AWS (pilot) | Notes |
|---|---|---|
| Ingestion (Kafka) | **Amazon MSK** (or self-managed Kafka on EC2) | MSK = less ops; self-managed = closer to on-prem parity |
| Stream processing (Flink) | **Amazon Managed Service for Apache Flink** or Flink on EC2 | stateful features/CEP |
| Online feature store / cache | **ElastiCache for Redis** | sub-ms feature serving |
| Analytics/investigation store | **ClickHouse on EC2** (EBS gp3) | keep in-region; ClickHouse Cloud only if region-compliant |
| Model serving | **ONNX Runtime / Triton on EC2** (CPU inference; **g5/p4d** for training) | |
| App / API (FastAPI) | **EC2 / ECS / EKS** | behind ALB |
| Dashboard (React) | **S3 + CloudFront** (static) or served by app | |
| App metadata DB | **Amazon RDS for PostgreSQL** | cases, users |
| Object store (models/datasets) | **S3** (SSE-KMS, versioned, object-lock) | |
| Orchestration | **MWAA (Managed Airflow)** or Airflow on EC2 | |
| Secrets | **AWS Secrets Manager / SSM Parameter Store** | holds `NEAR_AI_API_KEY`, `GROQ_API_KEY`, `PII_HMAC_KEY` |
| Keys | **AWS KMS** (or **CloudHSM**) | encryption at rest |
| Identity | **Keycloak on EC2** (or Cognito) | OIDC/OAuth2 |
| Observability | **Prometheus/Grafana on EC2** + CloudWatch | |

**Lightsail vs EC2:** Lightsail is fine for a **pure demo** (fixed-price, simple, a couple of instances). For a realistic pilot with proper sizing, GPU training, VPC isolation, and the streaming stack, **use EC2 inside a VPC.** Don't run the production-shaped pilot on Lightsail.

### 26.2 Security on AWS (Part 19 applies, AWS-specific)
- **VPC** with **private subnets** for data/compute; only the **ALB** in a public subnet; **security groups + NACLs** least-open.
- **Controlled egress for the LLM:** a **NAT gateway with egress allow-listed to only the NEAR AI + Groq endpoints** — everything else has **no internet egress** (preserves the air-gap spirit; only the tokenized, TEE-protected LLM traffic leaves).
- **IAM least-privilege roles** (no long-lived keys); **KMS** encryption at rest; **mTLS** internally; **AWS WAF** on the ALB; **GuardDuty + Security Hub + Inspector** for threat detection and **CVE/vulnerability scanning** (Part 19.5); **CloudTrail** for cloud-side audit.
- Because **PII is tokenized before egress** and the LLM runs in a **TEE**, even the allow-listed outbound traffic carries no raw PII and is unreadable to the provider.

### 26.3 Cost-conscious pilot sizing (order of magnitude)
- 1–2 × `m6i.large/xlarge` (Kafka/Flink/app), 1 × `r6i.xlarge` (ClickHouse), 1 × ElastiCache node, 1 × `g5.xlarge` (occasional training), small RDS, S3. Scale up only as data volume grows.

### 26.4 Migration path AWS → on-prem (clean, by design)
Because every choice is open-source/self-hostable, migration is component-swap, not rewrite:
`MSK → self-managed Kafka` · `Managed Flink → Flink cluster` · `ElastiCache → Redis` · `RDS → PostgreSQL` · `S3 → MinIO` · `KMS → HSM` · `Secrets Manager → HashiCorp Vault` · `MWAA → Airflow`. **The external NEAR AI call migrates too:** swap it for an **on-prem confidential-compute node** (the bank's own **H100/H200 in TDX**) running **gpt-oss-120b** locally — so even the LLM angle becomes fully on-prem and air-gapped, with the same OpenAI-compatible interface and the same attestation guarantees. **Terraform** modules are parameterized for both targets (`target = aws | onprem`) so the same IaC builds either environment.

---

*End of Addendum II. The blueprint now spans: the original Parts 0–17 (strategy, architecture, models, data, features, dashboard, rollout, compliance), Addendum Parts 18–20 (inference pipeline, cybersecurity, per-layer technique justification with sources), and Addendum II Parts 21–26 (dataset creation, training, model storage, the full application, the TEE-attested LLM gateway, and the AWS pilot with a clean on-prem migration path).*

---
---

# ADDENDUM III — ENTERPRISE READINESS (the 80% that isn't the model)
### Parts 27–34: Model Risk & AI Governance · Data Governance & Privacy · Responsible AI/Fairness · Reliability (HA/DR/BCP/SRE) · Quality (Testing/CI-CD/Change) · Integration & Source Onboarding · Operating Model · Program Governance + Go-Live Checklist

> **Why this addendum exists (proactively added).** The ML models are perhaps **20%** of an enterprise-ready system. In a regulated bank, the other **80%** — governance, regulatory alignment, reliability, privacy, testing, integration, and the human operating model — is what separates a working prototype from a production system that can actually go live, pass an RBI inspection, and run for years. This addendum covers what a real deployment additionally requires, mapped to the specific Indian regulations that apply: the **DPDP Act 2023 + Rules 2025**, **RBI IT Governance (ITGRCA) Master Direction 2023**, **RBI Cyber Security Framework 2016**, **RBI Outsourcing of IT Services Directions 2023**, **RBI Fraud Risk Management MD 2024**, and the **RBI FREE-AI Framework 2025** — plus global standards (**SR 11-7** model risk, **CERT-In** incident reporting).

---

## PART 27 — MODEL RISK MANAGEMENT & AI GOVERNANCE

A bank cannot run fraud-decisioning models without a formal **Model Risk Management (MRM)** and **AI governance** programme. This is now explicit Indian regulatory expectation via **RBI's FREE-AI Framework (Aug 2025)** and aligns with global **SR 11-7**.

### 27.1 Align to RBI FREE-AI (7 Sutras, 6 pillars, board-approved AI policy)
FREE-AI is advisory but signals where RBI supervision is heading; build to it now.
- **7 Sutras (principles)** the system must demonstrably honour: **Trust, People First, Innovation, Fairness, Accountability, Explainability, Resilience.** Map each to a control already in this blueprint (e.g., Explainability → Part 20.6 + 25; Fairness → Part 29; Accountability → immutable audit + human-in-the-loop; Resilience → Part 30).
- **6 pillars:** Infrastructure, Policy, Capacity, Governance, Protection, Assurance.
- **Concrete obligations:** a **Board-approved AI Policy**; structured governance across the **AI lifecycle** (approval → testing → deployment → monitoring → retirement); **bias detection** (Part 29); **explainability**; an **AI incident-reporting** mechanism (use FREE-AI's indicative incident form); and **AI-specific clauses in outsourcing agreements** (covering algorithmic bias, third-party/subcontractor AI use, and data confidentiality — directly relevant to your AWS + NEAR AI vendors).

### 27.2 The MRM framework (SR 11-7-style, the global backbone)
- **Model inventory** — every model (L2–L6, the LLM gateway) registered with owner, purpose, risk tier, data, version, validation status.
- **Model risk tiering** — tier by impact (a transaction-blocking-influencing model is higher-tier than a narrative LLM); higher tiers get deeper validation and more frequent review.
- **Independent validation** — a function **separate from the developers** validates conceptual soundness, data, performance, stability, and outcomes (the "effective challenge" principle). The LLM narrative gateway gets validated for grounding/hallucination, not just accuracy.
- **Model documentation** — a full **model card** per model (intended use, training data + hash, features, metrics, limitations, known failure modes, fairness results) — also the natural-justice evidence base.
- **Ongoing monitoring** — drift, performance decay, stability, and **outcome analysis** against realized fraud (Part 10).
- **Change & approval workflow** — model changes go through documented review → validation → approval → controlled deployment; **model retirement** is governed too.
- **Governance bodies** — an **AI/Model Risk Committee** (with risk, compliance, business, tech) approves models and reviews incidents; reports up to the Board (ties to the SCBMF/Audit-Committee chain in the original doc).

### 27.3 What's specific to ML (vs traditional models)
Data drift, feedback-loop effects (your EDD loop can amplify bias if unmanaged), non-stationarity, explainability of complex models, and adversarial robustness (Part 19) — all explicitly in scope for validation.

---

## PART 28 — DATA GOVERNANCE & PRIVACY

This system processes the personal data of **employees** (and customers) at scale — squarely within India's new privacy regime. Get this wrong and the penalties are up to **₹250 crore**.

### 28.1 DPDP Act 2023 + DPDP Rules 2025 (notified Nov 2025; ~18-month runway to full effect ~May 2027)
- **The bank is a Data Fiduciary** and will almost certainly be a **Significant Data Fiduciary (SDF)** given data volume/sensitivity → SDF obligations: appoint an **India-resident Data Protection Officer (DPO)**; conduct an **annual DPIA + independent data-protection audit**; and perform **due diligence on algorithmic/technical systems** ("algorithmic risk verification") — i.e., this fraud system's models are explicitly in scope for DPDP algorithmic due diligence.
- **Lawful basis for employee monitoring** — DPDP's "legitimate uses" is a **closed list, narrower than GDPR**. Fraud monitoring of staff must be mapped to a valid basis and documented; engage **legal + HR** early (Part 19.6). Conduct a **DPIA specifically for the employee-monitoring use case**.
- **Cross-border transfer (the LLM angle)** — sending data outside India is subject to DPDP transfer restrictions. Your design already mitigates this: **PII is hashed/tokenized before egress** (Part 25.3) and the **TEE** prevents provider access — but document the transfer, confirm the destination isn't a restricted jurisdiction, and prefer the **on-prem self-hosted gpt-oss migration** (Part 26.4) for full residency.
- **Data minimization, purpose limitation, retention & erasure** — collect only what the detection needs; define **purpose-bound retention timelines**; automate lifecycle deletion; honour erasure with carve-outs for legal/fraud-investigation obligations.
- **Data-principal rights** — access, correction, erasure, grievance — with response SLAs.
- **Breach notification** — personal-data breaches to the **Data Protection Board + affected principals**; coordinate with **CERT-In incident reporting (6-hour rule)** and RBI cyber-incident reporting. Distinguish personal-data breaches from general cyber incidents.

### 28.2 Data management foundations (enterprise data governance)
- **Data catalog + data dictionary** — every field in the unified event model documented, owned, and classified.
- **Data classification** — tag PII/PAN/sensitive vs operational; drives masking, access, and retention.
- **Data quality** — validation rules at ingestion (completeness, validity, freshness, schema conformance); quality SLAs and dashboards (bad data → bad detection).
- **Data lineage** — end-to-end (source → feature → model → alert), for audit, debugging, and DPDP traceability.
- **Schema registry & evolution** — a **schema registry** (e.g., Confluent/Apicurio) governs event schemas; backward/forward-compatible evolution so source-system changes don't break the pipeline.
- **Master Data Management (MDM)** — consistent entity resolution (one employee, one customer identity) across CBS/HR/IAM — essential for the entity-360 and graph layers.
- **Retention & archival** — tiered (hot ClickHouse → cold object store → archive), aligned to DPDP retention and RBI record-keeping.

---

## PART 29 — RESPONSIBLE AI: FAIRNESS, BIAS & ETHICS

A system that flags **employees** for potential fraud carries serious fairness and reputational risk; FREE-AI's **Fairness** and **People First** Sutras make this a regulatory expectation, not just good practice.

### 29.1 Bias & fairness auditing
- **Test for disparate impact across employee attributes** — grade/seniority, age, gender, region/branch, department, tenure. The model must not systematically over-flag any group beyond what genuine risk justifies.
- **Fairness metrics** — measure and monitor (e.g., demographic-parity difference, equal-opportunity / equalized-odds gaps, disparate-impact ratio) at deployment **and continuously** (bias can drift).
- **Mitigations** — peer-group-relative scoring (already in the design) reduces some bias; additionally apply pre-/in-/post-processing fairness techniques where gaps appear; **never use protected attributes as features**, and watch for **proxies** (e.g., branch as a proxy for region/caste/religion).
- **The feedback-loop fairness trap** — if investigators disproportionately confirm certain groups, the EDD loop learns and amplifies it. Monitor label distributions for this and correct.

### 29.2 Ethics, oversight & accountability
- **Human-in-the-loop is mandatory** — the system flags; a human decides; natural-justice hearing precedes any classification (DPDP + RBI + the Supreme Court ruling in the original doc).
- **AI ethics / governance committee** — reviews fairness results, high-impact decisions, and incidents; includes diverse stakeholders.
- **Transparency to staff** — employees should know monitoring exists, its purpose, and recourse (proportionality + works-council/union/legal engagement).
- **Explainability as a right** — every alert carries reason codes + narrative (Parts 20.6, 25) so decisions are contestable and defensible.
- **The "watch the watchers" principle** (Part 19) — investigators' actions are themselves audited and subject to fairness review.

---

## PART 30 — RELIABILITY ENGINEERING: HA, DR, BCP & SRE

RBI's ITGRCA Master Direction makes **Business Continuity (BCP)** and **Disaster Recovery (DR)** mandatory, board-approved, and regularly tested — not optional.

### 30.1 High availability & disaster recovery (RBI ITGRCA)
- **RTO/RPO targets** — define per component (e.g., alerting RTO minutes, RPO near-zero for the audit log); document and test against them.
- **Redundancy** — multi-AZ (AWS pilot) / multi-DC (on-prem prod) for Kafka, ClickHouse, Redis, app, model-serving; no single point of failure (an explicit ITGRCA vendor-risk requirement).
- **Backup & restore** — automated, encrypted, **immutable** backups (esp. the audit log and model registry); **regular restore drills** (a backup you haven't restored is a hope, not a plan).
- **DR site + failover runbooks** — a tested DR environment; documented, rehearsed failover; **cyber-resilience drills** (ITGRCA explicitly calls for regular cyber drills).
- **Business Continuity Plan** — board-approved BCP covering this system; periodic BCP testing; degradation modes (the system falls back to rules if ML is down — Part 18 — a continuity feature).
- **Chaos engineering** — proactively inject failures (kill a broker, a serving node) to validate resilience before reality does.

### 30.2 Observability & SRE
- **SLOs / SLIs / error budgets** — define service-level objectives (e.g., alert-pipeline availability 99.9%, p99 scoring latency, alert-delivery freshness) with error budgets that gate change velocity.
- **The four golden signals** — latency, traffic, errors, saturation — per component.
- **Distributed tracing** — **OpenTelemetry** across the event → feature → score → alert path, so you can debug a slow or wrong alert end-to-end.
- **Centralized logging** — structured logs (the system's own ops logs, distinct from the immutable audit log) searchable in ClickHouse/OpenSearch.
- **Metrics & dashboards** — Prometheus + Grafana for infra and model health; capacity dashboards.
- **Alerting & on-call** — operational alerts (pipeline lag, drift, node down) routed to an **on-call rotation** (PagerDuty/Opsgenie) with severity tiers.
- **Incident management** — defined severity levels, incident commander role, runbooks, and **blameless post-mortems**; tie cyber incidents into RBI/CERT-In reporting.
- **Capacity management** — **annual capacity assessment reviewed by the IT Strategy Committee** (an explicit ITGRCA requirement); proactive scaling as transaction/telemetry volume grows.

---

## PART 31 — QUALITY ENGINEERING: TESTING, CI/CD & CHANGE MANAGEMENT

Enterprise software in a bank needs a real test strategy — and ML adds **data and model testing** on top of normal software testing.

### 31.1 Test strategy (software + ML)
- **The test pyramid (software):** unit → integration → contract (API) → end-to-end. Target high coverage on the rules engine, feature transforms, scoring service, and API.
- **Data validation tests** — schema conformance, range/null checks, freshness, distribution checks at ingestion (e.g., Great Expectations / Pandera). Bad data is the #1 cause of silent model failure.
- **ML-specific testing** (beyond accuracy):
  - **Behavioral tests** — assert known fraud patterns score high and known-benign patterns score low (use the synthetic red-team library, Part 21).
  - **Metamorphic / invariance tests** — e.g., scaling a transaction amount up should not *decrease* its risk; changing an irrelevant field should not change the score.
  - **Directional-expectation tests** — off-hours + new-beneficiary + high-value should raise risk monotonically.
  - **Model regression tests** — a new model must not regress on a fixed evaluation set or on previously-caught cases.
  - **Drift / data-integrity tests** in production (Part 10).
  - **Fairness tests** (Part 29) gated in CI.
- **Performance & load testing** — sustained and burst throughput at target TPS; p99 latency budgets; soak tests.
- **Chaos & resilience testing** (Part 30.1).
- **Security testing** — SAST/DAST/IAST, dependency/CVE scans, **VAPT** (RBI ITGRCA-mandated), and **ATLAS-based adversarial-ML red-teaming** (Part 19).
- **UAT** — fraud investigators validate the dashboard and workflow before go-live.

### 31.2 CI/CD & environments
- **Environments** — dev → staging (prod-like, masked data) → production; strict parity via IaC.
- **CI pipeline** — lint → unit/integration → data-validation → model behavioral/fairness tests → security scans → build signed artifacts/images.
- **CD pipeline** — **GitOps** (e.g., ArgoCD), **blue-green / canary** deploys, automated rollback on SLO/metric regression, **feature flags** for safe toggling.
- **Model CD** — shadow → champion/challenger → canary (Part 22.3), with signature verification on load (Part 23).

### 31.3 Change management (ITIL, regulator-facing)
- **Formal change management** — change requests, risk assessment, CAB approval for production changes, scheduled windows, documented rollback — expected under RBI ITGRCA.
- **Rule/threshold changes** are change-controlled (Part 24.1) with four-eyes approval and audit (a rule change can blind detection — treat it like a model change).
- **Release governance** — versioned releases, release notes, traceability from requirement → code → test → deploy.

---

## PART 32 — INTEGRATION ARCHITECTURE & SOURCE-SYSTEM ONBOARDING

The system is only as good as its feeds. Integrating with a bank's legacy estate is a major work-stream in its own right — and using AWS/NEAR AI makes parts of it **outsourcing** under **RBI Outsourcing of IT Services Directions 2023** (vendor due diligence, SLAs, exit strategy, audit rights, concentration risk).

### 32.1 Integration layer
- **Ingestion adapters per source** — purpose-built connectors:
  - **CBS** (Finacle / Flexcube / BaNCS / T24) — transaction/posting logs via CDC, batch extract, or message queue.
  - **Payments/SWIFT/RTGS/NEFT/UPI** — message logs (and the **SWIFT↔CBS reconciliation** join — the PNB control).
  - **IAM / Active Directory** — auth logs (often via the SIEM).
  - **PAM** (CyberArk / BeyondTrust) — privileged-session logs.
  - **IGA / entitlement** systems — entitlement-change events.
  - **HR / HRMS** — joiner-mover-leaver feed (the highest-value context signal).
  - **DB audit / DLP** — data-layer activity.
- **Pattern** — prefer **event-streaming (CDC → Kafka)** for low latency; **batch** where systems only export periodically (these feed the slow lane).
- **API gateway** — a managed gateway (Kong/APISIX/AWS API Gateway) fronting the app APIs: auth, rate-limiting, routing, observability.
- **Event-schema governance** — schema registry + versioning (Part 28.2) so a CBS upgrade doesn't silently break features.

### 32.2 Reliability patterns for integration
- **Idempotency** (dedupe by event_id), **retries with backoff**, **dead-letter queues** for poison messages, **circuit breakers** and **bulkheads** so one failing source doesn't take down the pipeline, **backpressure** handling (Part 18).
- **Reconciliation** — periodically reconcile ingested counts vs source-of-truth to detect silent feed loss (a missing feed = a blind spot a fraudster could exploit).

### 32.3 Source-onboarding playbook (repeatable per system)
For each new source: data discovery → schema mapping to the unified event model → connector build → data-quality rules → backfill historical data → validate lineage → enable in shadow → promote. Track each source's onboarding status on the program dashboard.

---

## PART 33 — OPERATING MODEL: ORG, RACI, STAFFING, WORKFLOW, SOPs, ADOPTION

Technology without an operating model fails. Who runs this, who acts on alerts, and how, is as important as the models.

### 33.1 Team structure & the Three Lines of Defense
- **Build/run teams:** Platform/SRE (runs infra), ML Engineering/Data Science (models + feedback loop), Data Engineering (pipelines/integration), Application Engineering (dashboard/APIs), Security (Part 19).
- **Use teams (the Three Lines, from the original doc):** **1st line** — Fraud/Vigilance investigators (triage + act on alerts); **2nd line** — Risk & Compliance (EWS/RFA, thresholds, model risk, FREE-AI governance); **3rd line** — Internal Audit (independent assurance, IS audit per RBI).
- **Governance:** AI/Model Risk Committee, Information Security Committee (ISC, RBI-mandated, head from risk), IT Strategy Committee (ITSC, board-level), and the SCBMF/Audit Committee (fraud, from the original doc).

### 33.2 RACI (illustrative, for key activities)
| Activity | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Alert triage & EDD | Investigator | Fraud Ops Lead | ML Eng (explanations) | Compliance |
| Block decision | Fraud Ops Lead | CRO/MLRO | Legal | Business line |
| Model deploy | ML Engineer | Model Risk Committee | Validation, Security | Audit |
| Rule/threshold change | Compliance | CRO | Fraud Ops | Audit |
| Incident response | SRE/Security | CISO | Vendor, RBI/CERT-In liaison | Board |
| Fairness review | Data Science | AI Ethics Committee | HR, Legal | Board |

### 33.3 Analyst workflow, staffing & escalation
- **Staffing model** — size the investigator team to the **alert volume the thresholds produce** (Part 14); the binding constraint. Plan shift coverage (insider fraud isn't 9–5).
- **Escalation matrix** — severity-based routing (e.g., high-risk + high-exposure → senior + Vigilance immediately); SLA/TAT timers (RBI ≤30-day examination).
- **Investigation playbooks / SOPs** — per typology (a beneficiary-fraud SOP differs from an exfiltration SOP); standardize EDD steps, evidence collection, and the **handoff to HR disciplinary and law-enforcement (CBI/ED) referral** (the enforcement chain from the original doc).
- **Knowledge management** — a living playbook/wiki; capture new typologies back into rules + the synthetic library (closing the loop).

### 33.4 Adoption & change management (human factors)
- **Training & enablement** — investigators trained on the tool *and* on interpreting AI output (and its limits); RBI ITGRCA also requires DPDP/security training for staff.
- **Trust calibration** — analysts must neither over-trust nor ignore AI; the explainability + feedback loop builds calibrated trust; track override rates.
- **Alert-fatigue management as an operational discipline** (Part 19/14) — monitor and tune relentlessly; fatigue is the #1 operational failure mode.
- **Feedback culture** — make EDD dispositions easy and valued (they are the training signal).

---

## PART 34 — PROGRAM GOVERNANCE, FINOPS, DOCUMENTATION & GO-LIVE READINESS

### 34.1 Program & delivery governance
- **Steering committee** (business, risk, tech, compliance) owns scope, budget, and the phased roadmap (Part 13); **program management** with a **RAID log** (Risks, Assumptions, Issues, Dependencies).
- **Success metrics / OKRs** — tied to Part 14 (time-to-detection reduction, precision@k, alert-to-fraud ratio, loss avoided) and adoption (analyst throughput, override rate). Review quarterly.
- **Stakeholder management** — the stakeholder map from Part 2 drives communication and sign-offs.

### 34.2 FinOps / cost / TCO
- **Cost monitoring** — track infra + LLM-API + license costs; tag resources; **showback/chargeback** to the fraud function.
- **TCO & build-vs-buy** — periodically re-evaluate vs commercial platforms (Part 3); right-size compute (Part 26.3); the escalation discipline (don't run costly deep models that don't earn their keep — Part 20) is also a FinOps control.
- **Capacity & cost forecasting** — annual (ties to RBI capacity-management requirement).

### 34.3 Documentation & knowledge assets
- **Architecture Decision Records (ADRs)** — capture why each major choice was made (e.g., LightGBM over deep nets; XGB-Graph over GNN; TEE LLM).
- **Runbooks & ops manuals**, **API docs** (OpenAPI), **data dictionary**, **model cards**, **SOPs/playbooks**, **DR/BCP plans** — all version-controlled and audit-accessible.

### 34.4 Vendor & third-party risk (RBI Outsourcing Directions 2023)
- **Vendor due diligence** for AWS and NEAR AI/Groq: security posture, SLAs, audit rights, data-handling, **exit strategy**, and **concentration-risk** mitigation. Apply **AI-specific outsourcing clauses** (FREE-AI): algorithmic bias, subcontractor AI use, data confidentiality. Maintain an **SBOM** (CERT-In v2.0, SPDX/CycloneDX) — aligns with RBI software-governance expectations.

### 34.5 Threat intelligence & continuous improvement
- Feed external **fraud typology intelligence** and threat intel into the rules + synthetic library; run periodic **red-team exercises** (Part 19); update the model and rules as fraud evolves (it always does).

### 34.6 Go-live readiness checklist (consolidated)
**Regulatory & governance:** ☐ Board-approved AI policy (FREE-AI) ☐ Model inventory + tiering + independent validation (MRM/SR 11-7) ☐ DPDP: DPO appointed, DPIA done (incl. employee-monitoring), lawful basis documented, cross-border transfer assessed ☐ Fairness/bias audit passed (Part 29) ☐ RBI ITGRCA controls (ISC, BCP/DR, VAPT, IS audit, capacity) ☐ AI incident-reporting process (FREE-AI) + CERT-In/RBI reporting wired.
**Security:** ☐ Threat model + STRIDE/ATLAS ☐ VAPT + adversarial-ML red-team passed ☐ PAM for own admins, least-privilege, immutable audit ☐ SBOM + dependency/CVE scans clean ☐ Secrets in vault, keys in HSM/KMS, PII tokenization verified.
**Reliability:** ☐ RTO/RPO defined + DR drill passed ☐ Backups + restore drill ☐ SLOs/SLIs + on-call + runbooks ☐ Chaos test passed ☐ Graceful degradation (rules-only fallback) verified.
**Quality:** ☐ Test suite (incl. ML behavioral/metamorphic/fairness) green in CI ☐ Load/p99 latency targets met ☐ UAT signed off by investigators ☐ Change-management/CAB process live.
**Data & integration:** ☐ Each source onboarded + reconciled + lineage verified ☐ Data-quality SLAs + schema registry ☐ Retention/erasure automated.
**Operating model:** ☐ Investigator team staffed/trained to alert volume ☐ Escalation matrix + SOPs/playbooks ☐ RACI agreed ☐ Feedback loop operational.
**Program:** ☐ Steering committee + RAID + OKRs ☐ Vendor due diligence (AWS/NEAR AI) + exit strategy ☐ Documentation/ADRs/model cards complete.

---

*End of Addendum III. The blueprint now covers the full lifecycle of a regulated, enterprise-grade insider-fraud detection platform — strategy and architecture (0–17), inference/security/model-selection (18–20), build mechanics (21–26), and the enterprise-readiness layer of governance, privacy, fairness, reliability, quality, integration, operating model, and go-live (27–34) — aligned to the DPDP Act, the RBI IT-Governance, Cyber-Security, Outsourcing, Fraud, and FREE-AI frameworks, and global model-risk and adversarial-ML standards. The ML is ~20%; this addendum is the 80% that makes it real.*
