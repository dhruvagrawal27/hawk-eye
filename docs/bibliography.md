# Bibliography & Key References

> **Owner:** PLATFORM (Laptop 06) · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 17.D** ("Key references — for the team to read").
> This file reproduces the blueprint's reference list and groups it for navigation. It is the
> canonical "further reading" index for the Hawk-Eye program; every design choice in this repo
> traces back to one or more of these sources (see also [`adr/README.md`](./adr/README.md) and
> the per-layer technique justifications in blueprint Part 20).

---

## A. Base rates, regulation & natural justice

- **ACFE — *Occupational Fraud 2024: Report to the Nations*.** Base rates; the "detection-by-tips
  dominates" reality the system is built to move the needle on.
- **RBI — *Master Directions on Fraud Risk Management* (July 15, 2024).** EWS framework, RFA
  tagging, CRILC (₹3-crore / 7-day) reporting, 180-day classification, FMR, Central Fraud
  Registry (CFR), Data Analytics & Market Intelligence Unit mandate.
- ***SBI v. Rajesh Agarwal* (Supreme Court of India, 2023).** Natural justice — the accused must
  be heard before a fraud classification. This makes Hawk-Eye's **alert-only / human-in-the-loop**
  design *required*, not merely prudent.

> Program-wide regulatory anchors used across this repo (beyond Part 17.D, for completeness):
> **DPDP Act 2023 + DPDP Rules 2025**, **RBI ITGRCA 2023**, **RBI Cyber Security Framework 2016**,
> **RBI Outsourcing of IT Services Directions 2023**, **RBI FREE-AI 2025** (7 Sutras / 6 pillars),
> **SR 11-7** (model risk), **CERT-In** (6-hour incident reporting).

---

## B. Insider-threat datasets & surveys

- **CMU-SEI CERT** Insider Threat dataset (releases r4.2 / r5.2 / r6.2) & associated papers.
- **SPEDIA** insider-threat prototyping data.
- ***Deep Learning for Insider Threat Detection: a Review*** — arXiv **2005.12433**.

---

## C. Time-series / sequence anomaly detection (feeds L4)

- **USAD** — *UnSupervised Anomaly Detection on multivariate time series* (KDD 2020).
- **TranAD** — VLDB 2022, arXiv **2201.07284**.
- **Anomaly Transformer** — ICLR 2022.
- ***Towards a Rigorous Evaluation of Time-Series Anomaly Detection*** — the **point-adjust
  critique** (why naive point-adjusted metrics make random scores look great; we avoid it).
- **LAXCAT** — *Explainable Multivariate Time Series Classification* (Hsieh, Wang, Sun, Honavar,
  2020; arXiv **2011.11631**). The explainable, supervised L4 option.

---

## D. Graph / relational fraud detection (feeds L5)

- ***Graph Neural Networks for Financial Fraud Detection: A Review*** — arXiv **2411.05815**.
- **safe-graph / graph-fraud-detection-papers** (GitHub) — curated reading list.
- ***Finding money launderers using heterogeneous GNNs*** (DNB / Norges Bank, 2025).

---

## E. Tabular & graph fraud datasets

- **IEEE-CIS** fraud dataset.
- **ULB Credit-Card-Fraud** dataset.
- **PaySim** (scale testing — *mind the balance-column leakage*).
- **Elliptic** (graph prototyping).
- ***Fraud Dataset Benchmark*** (Amazon) — arXiv **2208.14417**.

---

## F. Architecture & platform references

- **ClickHouse for security analytics** — Exabeam, IBM QRadar case studies.
- **Kafka + Flink real-time fraud** architecture references.

---

## G. Vendor framings to study (and surpass)

- **Feedzai** — *RiskOps / TRUST*.
- **Featurespace** — *Adaptive Behavioral Analytics*.
- **NICE Actimize.**
- **DataVisor** — unsupervised.
- **Securonix / Exabeam** — UEBA.

---

## Cross-references inside this repo

- Per-layer head-to-head technique selection with paper citations: **blueprint Part 20**.
- Model-by-layer / dataset / tech-stack cheat sheets: **blueprint Part 17.A / 17.B / 17.C**.
- Model cards index (the real cards come from ML training): [`model-card-index.md`](./model-card-index.md).
- Detection coverage & honest limits: [`detection-coverage-map.md`](./detection-coverage-map.md),
  [`honest-limits.md`](./honest-limits.md).

---

*Source of truth: blueprint Part 17.D. Grouping and the cross-repo pointers are editorial; the
reference list itself is reproduced from the blueprint.*
