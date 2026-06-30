# Module: `lightsail-instances` (PLATFORM-7) — SCAFFOLD · CHOSEN PILOT

A single **AWS Lightsail instance** (Ubuntu 22.04, fixed-price bundle) that runs the
**docker-compose stack** (`deploy/compose`) for the synthetic-data demo/pilot.

- **This is the program's chosen pilot target** (see `docs/adr/ADR-0001-ec2-in-vpc.md`)
  — a deliberate, documented deviation from the blueprint's EC2-in-VPC default.
- `user_data` installs Docker + Compose; the BOM-pinned stack is brought up
  out-of-band. **No GPU on Lightsail** — deep training stays on AWS/on-prem GPU
  (ADR-0002); the demo serves pre-trained ONNX on CPU.
- Must stay in **ap-south-1** for data residency (Part 16).
- **SCAFFOLD:** plan-only, never applied.
