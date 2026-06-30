# tee-attestation (PLATFORM-14, MOCK)

Mock confidential-compute attestation gateway. Blueprint **Part 25.2/25.4**, **Part 26.2/26.4**.

**MOCK** — no real TEE hardware here. Simulates the NEAR AI gateway's per-request
**dual attestation** (Intel TDX CPU + NVIDIA H200 GPU), signed with a local Ed25519 key,
and a verifier. Enforces **tokenize-before-egress** (Part 25.3): a prompt containing raw
PII is rejected — no quote issued.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/attest` | `{prompt, model, provider}` → signed dual quote + audit memo (`provider, tee_attested, attestation_id, model, prompt_hash, ts`) |
| POST | `/verify` | verify a quote → `{valid, reasons}` |
| GET | `/pubkey` | mock signing public key |
| GET | `/health`, `/metrics` | liveness + Prometheus |

## Behaviour
- `provider=near_ai` → full TEE path: `tee_attested=true`, dual quote, `enclave_mode`
  reflects `TEE_ENCLAVE_MODE` ("TLS terminates inside the enclave").
- `provider=groq` → **not a TEE path** (Part 25.4): `tee_attested=false`, still tokenized,
  logged degradation.
- Raw PII in the prompt → `422` (tokenize-before-egress, Part 25.3).

## Real swap (Part 26.4)
On-prem **H100/H200-in-Intel-TDX** node running **gpt-oss-120b** emits real TDX + NVIDIA
quotes; this verifier is replaced by genuine attestation verification. Node profile:
`deploy/profiles/onprem-llm-node.yaml`. Audit-memo fields match **BACKEND.md §7**.

## Demo
```bash
curl -s localhost:8090/attest -d '{"prompt":"Alert EMP-7f3a paid BEN-9b1c INR 48,00,000 off-hours","provider":"near_ai"}' | tee /tmp/q.json
curl -s localhost:8090/verify -d @/tmp/q.json
```
