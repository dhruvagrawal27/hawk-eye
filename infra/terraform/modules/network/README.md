# Module: `network` (PLATFORM-7) — SCAFFOLD

The private-first VPC for the AWS pilot. Implements Part 26.2's isolation model.

## Topology
- **3 subnet tiers** across the AZs in `var.azs`:
  - `data` (private, **no default route** — true air-gap): MSK, ElastiCache, RDS.
  - `compute` (private, route to NAT for the *one* allow-listed egress): Flink, EC2
    (ClickHouse / serving / Keycloak), MWAA.
  - `public` (the **only** internet-facing tier): the ALB, nothing else.
- **IGW** serves the public/ALB subnet. **NAT gateway** is the single controlled
  egress chokepoint for the compute tier. The data tier has no NAT route at all.

## Egress allow-list (the air-gap, Part 26.2 / Part 19.3)
Only the tokenized, TEE-protected LLM traffic may leave. The allow-list is:

| FQDN | Purpose |
|---|---|
| `cloud-api.near.ai` | NEAR AI confidential-compute LLM gateway |
| `api.groq.com` | Groq inference endpoint |

**Why a proxy/prefix-list is required:** AWS security groups and NACLs match on
**IP/CIDR/port, not FQDN**. The `compute` SG pins egress to `tcp/443` only, but the
actual FQDN allow-listing is enforced at apply time by **one** of:
1. a forward proxy (Squid/Envoy) with a domain allow-list in the public subnet, or
2. **Route 53 Resolver DNS Firewall** + an AWS-managed **prefix list** scoped to the
   two endpoints.

Everything not on the allow-list has **no internet egress**. The data tier route
table has no `0.0.0.0/0` entry, so PII-bearing stores literally cannot reach the
internet — preserving the on-prem air-gap spirit even on the cloud pilot. Because
PII is tokenized before egress and the LLM runs in a TEE (Part 25), even the
allow-listed traffic carries no raw PII.

## Defence in depth
- Least-open **security groups** per tier (ALB → compute → data, intra-VPC only).
- **NACLs** on the data subnets deny everything except intra-VPC (stateless layer).

## Migration (Part 26.4)
On-prem replaces this with physical/virtual network segmentation + an egress proxy;
see `migration-map.md`. SCAFFOLD: plan-only, never applied.
