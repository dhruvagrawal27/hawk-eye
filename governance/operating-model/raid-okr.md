# RAID Log & OKRs — Hawk-Eye Program (PLATFORM-39)

> Blueprint **Part 34.1** (program governance: steering committee + **RAID log** + OKRs) +
> **Part 14** (metrics). The Steering function is the **IT Strategy Committee** (board-level,
> Part 33.1 / `committee-charters.md`). OKRs are tied to Part 14 and reviewed **quarterly**.
> Current values are the **seeded operating metrics** (`governance/db/seed.py`,
> `operating_metrics`, period 2026-Q2). Model under review: **fusion-2026.2.0**.

---

## 1. RAID log (Risks, Assumptions, Issues, Dependencies)

### 1.1 Risks
| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R-01 | **Alert fatigue** floods investigators; real fraud missed (the #1 operational failure mode, Part 19/14). | High | High | Threshold governance to analyst capacity; track `alert_fatigue` (seeded 0.32) + `override_rate`; relentless tuning. | Fraud Ops Lead |
| R-02 | Model drift degrades detection silently (fusion-2026.2.0). | Med | High | PSI/drift monitoring; AMRC monthly review; rules-only fallback (Part 18). | Model Risk Cttee |
| R-03 | **Vendor concentration** (AWS + NEAR AI + Groq) / LLM egress. | Med | High | TEE attestation (NEAR AI) + tokenization + template fallback; on-prem migration readiness (Part 26.4). | ISC / ITSC |
| R-04 | Over-/under-trust of AI output (mis-calibration). | Med | Med | Explainability + EDD feedback; track `override_rate` (seeded 0.18) against target band. | Risk & Compliance |
| R-05 | Employee-monitoring fairness / legal exposure (system watches staff). | Med | High | DPIA `DPO-2026-004`; proportionate monitoring; transparency notice `HR-2026-011`; Ethics review `ETH-2026-006`. | DPO / AI Ethics |
| R-06 | ADR-0001 deviation (Lightsail vs Part 26 EC2-in-VPC) misread as non-compliance. | Low | Med | Documented deviation; on-prem in-India is production; scale-up path in FinOps TCO. | ITSC |
| R-07 | Investigator under-staffing vs alert volume (binding constraint, Part 14). | Med | High | Erlang-C sizing (`tools/staffing-calculator/`); 3-shift roster; revisit on threshold change. | Fraud Ops Lead |
| R-08 | False-block of a legitimate large transfer (itself a serious incident). | Low | High | **ALERT-ONLY** + HITL natural-justice gate; human decides, never the model. | CRO/MLRO |

### 1.2 Assumptions
| ID | Assumption |
|---|---|
| A-01 | **On-prem + synthetic-only** for the pilot; no real PII/creds; LLM egress tokenized + TEE-attested to NEAR AI/Groq only. |
| A-02 | Full telemetry available (transactions + identity/access + data-layer + change/HR) on the canonical actor→action→object schema. |
| A-03 | The EDD feedback loop produces labels; detection quality compounds month-over-month from operating the system. |
| A-04 | RBI TAT (≤30-day examination) and CERT-In (6h) reporting windows apply. |
| A-05 | Board AI policy (`BR-2026-014`, FREE-AI) and the seeded governance approvals are in force. |

### 1.3 Issues (open)
| ID | Issue | Status | Action |
|---|---|---|---|
| I-01 | `override_rate` 0.18 needs a calibrated target band (neither over- nor under-trust). | Open | Risk to set band; review next quarter. |
| I-02 | `precision_at_k` 0.71 vs analyst-capacity target. | Open | Tune threshold; re-check vs staffing calculator. |
| I-03 | `alert_fatigue` 0.32 above comfort. | Open | Tune rules + L6 weights; KM-wiki new typologies. |

### 1.4 Dependencies
| ID | Dependency | On |
|---|---|---|
| D-01 | Staffing sizing | `tools/staffing-calculator/staffing_calculator.py` (Erlang-C, 3-shift). |
| D-02 | Cost showback/chargeback + TCO | `tools/finops/finops.py` (Part 34.2). |
| D-03 | Independent model validation before deploy | Model Validation Unit (`MV-2026-007`, SR 11-7). |
| D-04 | Graceful degradation | `services/degradation-switch` (rules-only fallback, Part 18). |
| D-05 | Governance evidence | seeded governance DB (`governance/db/`) — committees, approvals, go-live ticks. |

---

## 2. OKRs (tied to Part 14 metrics; reviewed quarterly by the ITSC/Steering function)

> Baselines = seeded `operating_metrics` (period **2026-Q2**). "Loss avoided" and
> "alert-to-fraud ratio" are program metrics tracked via the EDD disposition log. Targets are
> illustrative program goals, to be ratified by the Steering Committee.

### Objective O1 — *Detect insider fraud far earlier, defensibly* (Part 14 headline)
| Key Result | Part 14 metric | Baseline (seeded 2026-Q2) | Target |
|---|---|---|---|
| KR1.1 | **Time-to-detection reduction** (mean-time-to-disposition `mttd`) | 4.5 (days) | ↓ to ≤ 2.0; months→minutes for digitally-observable schemes |
| KR1.2 | **Precision@k** | 0.71 | ≥ 0.80 at the analyst-capacity k |
| KR1.3 | **Alert-to-(true-)fraud ratio** | program-tracked (EDD log) | improve quarter-over-quarter; budget alerts, don't flood |

### Objective O2 — *Demonstrate business value* (Part 14 business)
| Key Result | Part 14 metric | Baseline | Target |
|---|---|---|---|
| KR2.1 | **Estimated loss avoided / caught-earlier** | program-tracked (EDD log + case value) | quantified per quarter; move the needle on the ACFE "tips dominate" reality |
| KR2.2 | Cases surfaced **by system vs by tips** | program-tracked | rising share surfaced by Hawk-Eye |

### Objective O3 — *Build calibrated trust and beat alert fatigue* (Part 33.4 adoption)
| Key Result | Metric | Baseline (seeded) | Target |
|---|---|---|---|
| KR3.1 | **Override rate** (trust calibration) | `override_rate` 0.18 | hold within a calibrated band (neither over-trust→0 nor ignore→1) |
| KR3.2 | **Alert fatigue** managed as operational discipline | `alert_fatigue` 0.32 | ↓ via relentless tuning; the #1 failure mode |
| KR3.3 | EDD disposition completeness (the training signal) | program-tracked | ≥ 95% alerts dispositioned within TAT |

> **Review cadence:** quarterly (Part 34.1). The Steering/ITSC reviews O1–O3 against the
> live `operating_metrics`; AMRC reviews model-linked KRs (fusion-2026.2.0); AI Ethics reviews
> fairness KRs. Cross-references: `raci-matrix.md`, `committee-charters.md`,
> `adoption-training.md` (trust calibration & alert-fatigue program), `sops/km-wiki.md`
> (closing the loop into rules + synthetic library).
