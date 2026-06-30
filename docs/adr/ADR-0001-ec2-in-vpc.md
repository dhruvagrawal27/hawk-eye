# ADR-0001 — Pilot deployment target: AWS Lightsail (documented deviation from the blueprint's EC2-in-VPC default)

- **Status:** Accepted
- **Date:** 2026-06-30
- **Owner:** PLATFORM (Laptop 06) · Task PLATFORM-8 · Blueprint Part 26.1 / 26.2 / 26.3 / 26.4, Part 9.3, Part 16
- **Deciders:** Platform/SRE, Program direction
- **Related:** ADR-0002 (compute placement), `infra/terraform/` (the `target = aws | onprem | lightsail` tree), `infra/terraform/migration-map.md`

## Context

The blueprint (Part 26.1, "Lightsail vs EC2") is explicit: **Lightsail is fine for a
*pure demo*** (fixed-price, simple, a couple of instances), but **for a realistic,
production-shaped pilot** with proper sizing, GPU training, VPC isolation, and the full
streaming stack, **use EC2 inside a VPC** — *"Don't run the production-shaped pilot on
Lightsail."* So the blueprint **default** is **EC2-in-VPC**.

The program, however, has directed that the **immediate pilot/demo** of Hawk-Eye runs
on **AWS Lightsail**. Hawk-Eye at this stage is a **single-tenant, synthetic-data,
alert-only demo** that runs the whole stack via `docker-compose` (`deploy/compose`).
For that shape, Lightsail's **fixed pricing** and **operational simplicity** are a good
fit, and none of the heavyweight reasons to prefer EC2-in-VPC (multi-AZ HA, GPU
training, fine-grained VPC isolation, managed streaming services) are needed *for the
demo itself*. The production target remains **on-prem, in-India** (Part 9.3, Part 16).

This ADR records that decision as a **deliberate, documented deviation** from the
blueprint default, and pins the relationship between the three targets so the IaC and
the team stay coherent. (The Terraform tree therefore exposes
`target = aws | onprem | lightsail`; all three paths are retained.)

## Decision

For **this project's demo/pilot, deploy on AWS Lightsail.**

- **Lightsail** = the **chosen demo/pilot** target (a single fixed-price instance
  running the compose stack; static IP; least-open public ports). `target = lightsail`.
- **EC2-in-VPC** = **retained as the scale-up pilot path** (the blueprint's
  production-shaped pilot: VPC isolation, multi-AZ, managed MSK/Flink/ElastiCache/RDS/
  MWAA/S3, WAF/GuardDuty/Inspector/CloudTrail). Not deleted — `target = aws`.
- **On-prem in-India** = the **production** target (self-hosted open-source mirror,
  Part 9.3 / Part 16). `target = onprem`. Migration is a clean component swap
  (`migration-map.md`, Part 26.4).

## Comparison matrix

| Criterion | **AWS Lightsail** (chosen demo/pilot) | **EC2-in-VPC** (scale-up pilot, blueprint default) | **On-prem in-India** (production) |
|---|---|---|---|
| **Cost** | Lowest, **fixed/predictable** monthly bundle | Variable, usage-based; higher; needs FinOps right-sizing (Part 26.3) | CapEx-heavy upfront; lowest marginal at scale; no cloud bill |
| **Simplicity / ops** | Highest — one instance, compose, static IP | Moderate — VPC, subnets, SGs/NACLs, managed services, IAM | Lowest — bank runs all infra (Ansible/Helm), but full control |
| **VPC isolation** | Minimal (Lightsail's lighter networking; ports firewalled per-instance) | **Strong** — private data/compute subnets, ALB-only public subnet, NACLs, allow-listed NAT egress | **Strongest** — physical/network segmentation, true air-gap |
| **GPU** | **None** on Lightsail | Yes (g5/p4d for occasional deep training) | Yes — bank's own H100/H200 (incl. TDX for the LLM) |
| **Streaming-stack fit** | Runs Kafka/Flink/etc. as **compose containers** on one host (demo scale) | **Best cloud fit** — managed MSK + Managed Flink + ElastiCache + RDS + MWAA | Self-hosted Kafka/Flink/Redis/Postgres/MinIO/Airflow at full scale |
| **Scale path** | Demo only; **scale up → EC2-in-VPC**, then **→ on-prem** | Scales to a real pilot; **migrates → on-prem** cleanly (Part 26.4) | Terminal production target |
| **Data residency (Part 16)** | `ap-south-1`, `data-residency: in-india` | `ap-south-1`, `data-residency: in-india` | In-India by construction |
| **GPU/LLM egress** | LLM via allow-listed egress (tokenized + TEE) | Same, via NAT allow-list to NEAR AI + Groq only | Fully on-prem LLM (gpt-oss-120b in TDX); **no egress** |

## Consequences

- **For the demo:** cheapest, simplest path to a running, shareable Hawk-Eye on
  synthetic data — exactly what the pilot needs now.
- **Trade-offs accepted (and bounded):** Lightsail gives weaker VPC isolation, no GPU,
  and no managed streaming services. These are **acceptable for a single-tenant,
  synthetic-data demo** and are *recovered* the moment we move to EC2-in-VPC or on-prem
  — both of which are fully built out in `infra/terraform/` and retained.
- **No GPU on Lightsail** ties to **ADR-0002**: deep training stays on AWS/on-prem GPU;
  the Lightsail demo serves pre-trained ONNX on CPU.
- **IaC stays target-parameterized:** one root tree, `target = aws | onprem | lightsail`,
  so choosing Lightsail now does not throw away the EC2-in-VPC or on-prem work.

## No golden rule is violated

1. **Alert-only** — deployment target is orthogonal to scoring/decisioning; the system
   still only scores and explains, never auto-blocks.
2. **On-prem + synthetic only** — the demo runs **synthetic** data; the **production**
   target stays **on-prem in-India**; Lightsail is only the interim demo host, pinned to
   `ap-south-1` / `in-india` for residency, with the same allow-listed-egress air-gap.
3. **Validate-against-blueprint** — this is a *documented* deviation from the Part 26.1
   default, with the blueprint's own caveat ("Lightsail is fine for a pure demo")
   honoured: we use it **only** for the pure synthetic demo, and we keep EC2-in-VPC as
   the production-shaped path exactly as the blueprint recommends.

## Alternatives considered

- **EC2-in-VPC for the demo now (the blueprint default).** Rejected *for the demo
  only*: higher cost + ops overhead than a single-tenant synthetic demo warrants.
  **Retained as the scale-up path** (`target = aws`) — not discarded.
- **On-prem from day one.** Rejected for the *pilot*: the bank's on-prem GPU /
  confidential-compute hardware is the production end-state, not the fastest path to a
  shareable demo. It remains the production target (`target = onprem`).
- **A different cloud / managed container service (ECS/EKS/Fargate).** Out of scope for
  the demo; EKS sits inside the EC2-in-VPC scale-up story if needed later.
