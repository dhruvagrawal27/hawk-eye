# ADR-0002 — Compute placement: CPU for trees + inference, GPU for deep train only

- **Status:** Accepted
- **Date:** 2026-06-30
- **Owner:** PLATFORM (Laptop 06) · Task PLATFORM-6 · Blueprint Part 9.1, Part 22.5, Part 20
- **Deciders:** Platform/SRE, ML Engineering

## Context
Hawk-Eye spans tree models (L3/L5 GBDT), deep sequence/graph nets (L4/L5 GNN), and a
high-throughput online inference path (L2–L6). GPUs are scarce and expensive; placing
work on the wrong tier wastes money or latency. The blueprint is explicit (Part 9.1):
*"GPU for training & graph, CPU for inference"*, and Part 20's recurring meta-lesson is
that tree/simple methods match or beat deep models on honest tabular/anomaly benchmarks.

## Decision
Three placement profiles (`deploy/profiles/compute-placement.yaml`):
1. **`tree-train` → CPU.** GBDTs train fast on CPU; GPU buys little and complicates ops.
2. **`seq-graph-train` → GPU.** Deep sequence (USAD/TranAD) and graph (GNN) training is the
   *only* tier that genuinely needs GPUs; uses a small, time-shared pool (Part 9.2).
3. **`inference` → CPU.** Online scoring of all layers runs on CPU via ONNX (trees + small
   nets), giving predictable low latency at low cost.

## Consequences
- **Cost:** GPU spend is bounded to occasional deep training (g5/p4d at low duty cycle —
  see the sizing calculator, PLATFORM-5). Inference fleet is cheap CPU.
- **Scaling discipline:** matches the blueprint's "escalation discipline" (don't run costly
  deep models that don't earn their keep — also a FinOps control, Part 34.2).
- **SCAFFOLD:** the GPU profile goes live only with real GPU hardware/quota. On Lightsail
  (ADR-0001) there is no GPU, so deep training runs on AWS/on-prem GPU and the Lightsail
  demo serves pre-trained ONNX on CPU.

## Alternatives considered
- *GPU for inference too* — rejected: trees/small nets don't need it; adds cost + ops.
- *All-CPU including deep training* — rejected: deep sequence/graph training is impractically
  slow on CPU at retrain cadence.
