# Architecture Decision Records (ADRs) — Index

> **Owner:** PLATFORM (Laptop 06) · **Task:** PLATFORM-40
> **Validated against blueprint:** **Part 34.3** — *"Architecture Decision Records (ADRs) — capture
> why each major choice was made (e.g., LightGBM over deep nets; XGB-Graph over GNN; TEE LLM)"* —
> all version-controlled and audit-accessible.

An **ADR** records a single significant architectural decision: its **context**, the **decision**,
and the **consequences** (and the alternatives considered). ADRs are **immutable once Accepted** —
we do not edit history; a later decision that reverses an earlier one gets a **new** ADR that
**supersedes** the old (the old ADR's status is updated to `Superseded by ADR-NNNN`). This gives
regulators and auditors a durable, traceable record of *why* the system is shaped the way it is.

---

## The ADR log

| ADR | Title | Status | Decision in one line | Blueprint |
|---|---|---|---|---|
| [ADR-0001](./ADR-0001-ec2-in-vpc.md) | Pilot deployment target: **AWS Lightsail** (documented deviation from EC2-in-VPC default) | Accepted (2026-06-30) | Deploy the synthetic-data, alert-only **demo** on **Lightsail**; **retain** EC2-in-VPC as the scale-up pilot and **on-prem in-India** as production | Part 26.1/26.2/26.3/26.4, Part 9.3, Part 16 |
| [ADR-0002](./ADR-0002-compute-placement.md) | **Compute placement**: CPU for trees + inference, GPU for deep train only | Accepted (2026-06-30) | `tree-train`→CPU, `seq-graph-train`→GPU, `inference`→CPU | Part 9.1, Part 22.5, Part 20 |

> **ADR-0001 is the program's one substantive, deliberate deviation** from the blueprint default
> (Part 26 recommends EC2-in-VPC for a production-shaped pilot; Lightsail is the chosen *demo*
> host). It is logged here and in CONTEXT.md §8. **On-prem in-India remains the production target**
> and **no golden rule is affected** (still on-prem-capable, synthetic, alert-only).

---

## The ADR process

1. **Propose.** When a decision is significant (it constrains other workstreams, deviates from the
   blueprint, or is costly to reverse), draft an ADR using the template below. New number =
   next free `ADR-NNNN`.
2. **Cite the blueprint.** Every ADR header names the **Part(s)** it validates against (golden
   rule: *validate-against-blueprint*). A deviation must say so explicitly and justify it.
3. **Decide.** Status moves `Proposed → Accepted` (or `Rejected`). Deciders are named.
4. **Check the golden rules.** Each ADR confirms it does not violate **alert-only**,
   **on-prem + synthetic-only**, or **validate-against-blueprint** (ADR-0001 has a dedicated "No
   golden rule is violated" section as the worked example).
5. **Immutable.** Once `Accepted`, the ADR is not edited; reversal = a new superseding ADR.
6. **Audit-accessible.** ADRs are version-controlled in `docs/adr/` and surfaced to governance
   (they support the MRM rationale — Part 27 — and the board pack via governance-api).

### File naming

`ADR-NNNN-short-slug.md` (e.g. `ADR-0001-ec2-in-vpc.md`). NNNN is zero-padded and monotonic.

### Template

```markdown
# ADR-NNNN — <decision title>

- **Status:** Proposed | Accepted | Rejected | Superseded by ADR-MMMM
- **Date:** YYYY-MM-DD
- **Owner:** <workstream> · Task <ID> · Blueprint Part <N.N>
- **Deciders:** <roles/bodies>
- **Related:** <other ADRs / files>

## Context
<the forces at play; what the blueprint says; why a decision is needed>

## Decision
<the choice, stated plainly>

## Consequences
<positive + negative; trade-offs accepted; SCAFFOLD/MOCK flags>

## No golden rule is violated   (required for any deviation)
<alert-only · on-prem+synthetic · validate-against-blueprint>

## Alternatives considered
<what else was on the table and why it was not chosen>
```

---

*Source of truth: blueprint Part 34.3. The two existing ADRs are owned by PLATFORM; this index is
maintained alongside them.*
