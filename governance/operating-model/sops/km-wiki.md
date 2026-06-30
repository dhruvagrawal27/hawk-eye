# Knowledge-Management Wiki — Closing the Loop (PLATFORM-39)

> Blueprint **Part 33.3** (knowledge management — *a living playbook/wiki; capture new
> typologies back into rules + the synthetic library, closing the loop*) + **Part 34.5**
> (threat intelligence & continuous improvement). This is the living KM artifact: it turns
> every novel pattern an investigator finds into a **new rule** and a **new synthetic
> red-team scenario**, so the system learns what the institution learns. The model under the
> current review cycle is **fusion-2026.2.0**.

---

## 1. Why this exists — the loop

Operating the system *is* how it gets smarter (Part 11/15). Two feedback loops run:

1. **The EDD label loop** (automatic) — every disposition (fraud / FP / inconclusive) is a
   label that feeds L3/L4 retraining. (Owned by ML Eng; out of scope for this wiki.)
2. **The typology loop** (this wiki, human-curated) — when an investigator discovers a
   **pattern the system did not encode**, it is captured here and pushed back into:
   - the **rules engine / BRE** (a new deterministic L1 rule on the SoD/toxic-combination
     matrix), and
   - the **synthetic red-team library** (a new scenario in the agent-based simulator, Part 7),
   so future synthetic training data and future rule coverage both include it.

```
   new typology found in EDD ─► KM-wiki entry ─► (a) new L1/BRE rule
                                              └─► (b) new synthetic red-team scenario
                                                       │
                                                       ▼
                                          better detection next cycle ─► (loop)
```

---

## 2. How to capture a new typology (procedure)

1. **Open a KM entry** using the template (§4). Anyone in the 1st/2nd line may author;
   reviewed by the Fraud Ops Lead + a Risk/Compliance representative.
2. **Describe the signal in canonical terms** — express it as actor→action→object events and,
   where relational, as a graph pattern (so it maps cleanly to a rule or a GNN feature).
3. **Propose the rule** — draft the deterministic L1/BRE condition (or the L5 graph pattern).
   Rule/threshold changes are **2nd-line owned** and go through the **CAB** (RACI 2.4;
   reference `CAB-2026-033`). Never auto-block — the new rule still produces an **alert**.
4. **Propose the synthetic scenario** — specify how the agent-based simulator should generate
   the typology (temporal/velocity/multi-account structure preserved). Hand to the data/ML team
   for the synthetic library.
5. **Update training** — if it changes investigator practice, add/extend the relevant SOP and
   trigger an M3 refresh (`../adoption-training.md`).
6. **Record provenance** — link the originating case, the EDD disposition, and the resulting
   rule + scenario IDs. Audit (3rd line) can trace the loop end-to-end.

---

## 3. Seed coverage (the typologies already encoded)

These ship in the SOP set and the rule/synthetic baseline; new entries extend them.

| Typology | SOP | Encoded as |
|---|---|---|
| New-beneficiary → high-value payment | `beneficiary-fraud.md` | L1 rule + L3 SHAP + L5 maker-checker |
| Off-hours / pre-resignation bulk export | `exfiltration.md` | L1 rule + L4 sequence |
| DB-write-without-app-txn / self-grant | `privileged-db-manipulation.md` | L1 rule + L4 + L5 entitlement chain |
| Maker-checker collusion / mule ring | `collusion-ring.md` | L5 graph |
| Dormant-reactivation → drain | `dormant-takeover.md` | L1 rule + L4 sequence |
| SWIFT↔CBS mismatch, suspense lapping | (rules baseline, Part 4/6) | L1 reconciliation rule |

---

## 4. New-typology entry template

```
### KT-YYYY-NNN — <short name>
- Discovered: <date> · Author: <name/role> · Source case: <case id / EDD disposition>
- Signal (canonical): actor→action→object pattern (and graph pattern if relational)
- Why current coverage missed it:
- Proposed L1/BRE rule (or L5 graph pattern):
- Proposed synthetic red-team scenario (simulator spec):
- SOP impact: <new/updated SOP + M3 refresh? yes/no>
- Review: Fraud Ops Lead ____  · Risk/Compliance ____  · CAB ref ____
- Status: proposed | rule-live | synthetic-live | closed
```

> **(No live KT entries yet — this is the living register; entries are appended here as the
> 1st line discovers new tradecraft.)**

---

## 5. External threat intelligence (Part 34.5)

Beyond internally-discovered typologies, feed **external fraud-typology intelligence** and
threat intel into the same loop (rules + synthetic library), and run periodic **red-team
exercises** (Part 19). New external typologies are logged here with the same template, tagged
`source: external-intel`. The system is updated as fraud evolves — because it always does.

Cross-references: `../adoption-training.md` (M3 + feedback culture), `../raci-matrix.md`
(rule/threshold change ownership + CAB), `../raid-okr.md` (alert-fatigue/precision OKRs the
loop improves), the SOPs in this directory.
