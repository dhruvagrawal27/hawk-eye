"""Hawk-Eye model-file registry (DATABASE laptop, DATABASE-7/8).

DATABASE owns the **object-store + registry LAYOUT, buckets, encryption,
object-lock, signing-at-rest, signature-verify-on-load, and access logging**.
ML owns the MLflow *tracking server runtime* + the ONNX packaging/signing that
happens during training. We consume the artifacts ML produces and expose the
layout + verification utilities ML and BACKEND call (blueprint Part 23, Part 19.2).
"""
