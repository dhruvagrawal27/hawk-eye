# SOP — Collusion Ring Investigation (PLATFORM-39)

> Blueprint **Part 33.3** (per-typology SOP) + **Part 5/7** (the hardest category:
> *maker-checker collusion, mule networks, toxic-combination-in-practice, insider+external
> rings*) — relational and invisible to tabular models; this is the **Layer-5 graph** tier.
> **ALERT-ONLY:** ends in a human decision; never auto-blocks.

## 1. Trigger (what fired)
A Hawk-Eye alert from the **L5 graph layer** (GraphSAGE/GAT heterogeneous GNN): a suspicious
**maker-checker collusion subgraph**, an **always-the-same maker-checker pair** (Part 6.2
pairing frequency), a **mule chain**, high degree/centrality in the beneficiary/counterparty
graph, or an **employee↔customer-account linkage**. Usually multi-actor and multi-account.

## 2. EDD steps
1. **Read the graph explanation** — the subgraph that fired: nodes (actors, accounts,
   beneficiaries), edges (maker↔checker, employee↔customer-account, fund flows), and centrality.
2. **Map the ring** — enumerate the actors and accounts; identify roles (who makes, who checks,
   who is the beneficiary, who is the external mule). Use the entity-360 view.
3. **Quantify the pairing** — how often does this exact maker-checker pair co-occur vs the
   population baseline? Persistent same-pair approval defeats SoD by collusion.
4. **Trace fund flows** — follow the money across accounts/beneficiaries; look for layering,
   round-tripping, and mule fan-out/fan-in patterns.
5. **Overlay context** — tenure, departments, branches, peer-group; are ring members linked
   off-system (same branch, reporting line, HR data)? Look for the trusted-veteran pattern.
6. **Corroborate carefully** — collusion EDD must not tip off **any** ring member; coordinate
   one discreet validation through the RACI Consulted path.

## 3. Evidence collection
- Export the **graph evidence** (subgraph, edges, centrality scores) plus the underlying
  per-actor events from the **immutable WORM audit log** for **every** ring member.
- Capture maker-checker co-occurrence stats and the fund-flow trace as the case file.
- Record chain-of-custody across all entities; build a single consolidated ring case (not N
  separate ones) so the relational picture is preserved.

## 4. Disposition (human decides)
- **True collusion** → request-block of the implicated flows via HITL gate; open a
  **consolidated multi-actor case**; CRO/MLRO accountable.
- **False positive** → close-as-FP (legitimate frequent pairing, e.g., small team).
- **Inconclusive** → hold the ring under heightened graph monitoring.
- Capture as labels (per actor); disposition within TAT.

## 5. Escalation
Confirmed ring or insider+external collusion → **Senior Investigator + Vigilance + CRO
immediately**; given multi-actor scope, brief the AMRC/SCBMF; consider parallel internal
investigation.

## 6. Handoff — HR disciplinary + law-enforcement referral
- **HR disciplinary:** evidence packages for **each** internal ring member to HR; natural
  justice / due process for each individually; coordinate simultaneous action to prevent
  evidence destruction.
- **Law-enforcement referral:** **CBI / ED** for the ring (collusion + mule networks are
  squarely criminal); file RBI FMR/CFR (Fraud MD 2024); Vigilance co-signs; Legal Consulted.
- Feed the ring topology into `km-wiki.md` → new graph rule + synthetic collusion-ring
  scenario (the synthetic red-team library, Part 7).
