# ATLAS Adversarial-ML Red-Team Report — Hawk-Eye (PLATFORM-23, MOCK)

> Blueprint **Part 19.4** (ATLAS-based red-teaming) + **Part 19.2** (ML-attack table) + **Part 13**.
> **MOCK** synthetic report — the exercise is a human/red-team act; this is the evidence
> artifact wired into the vuln tracker + governance DB (`security_reports` type=`redteam`,
> status `passed`). Tied to model version **fusion-2026.2.0**.

- **Engagement:** Q2-2026 adversarial-ML red-team · **Scope:** deployed L2–L6 models + LLM gateway
- **Methodology:** MITRE ATLAS tactics (Reconnaissance → ML Attack Staging → Exfiltration → Impact)
- **Result:** **PASSED** — 6 probes, **0 critical**, residual risks tracked. Sign-off: Red Team + Model Risk.

## Probes & outcomes (mapped to MITRE ATLAS)
| # | Attack (ATLAS) | Probe | Outcome | Residual / mitigation verified |
|---|---|---|---|---|
| 1 | **Evasion** (AML.T0043) | Craft activity just under thresholds; perturb feature values | **Contained** — peer-relative baselines + diverse ensemble (rules+unsup+sup+graph) meant evading one layer didn't evade all | Thresholds not exposed; randomized review sampling on |
| 2 | **Data/label poisoning** (AML.T0020) | Inject mislabeled EDD feedback; drift a behavioural baseline low-and-slow | **Detected** — SIEM `ABNORMAL_LABEL_EDITS` + `TRAINING_DATA_ANOMALY` fired; SoD segregates label/build; change-point baselines resisted | Immutable label audit; peer-anchored baselines |
| 3 | **Model inversion / membership** (AML.T0024) | Query the inference API to reconstruct sensitive attributes | **Contained** — internal-only, authenticated, rate-limited; raw scores not exposed; SIEM `MODEL_EXTRACTION_PATTERN` fired at volume | DP/regularization noted as future hardening |
| 4 | **Model extraction / theft** (AML.T0044) | Exfiltrate the model artifact for offline evasion crafting | **Blocked** — artifacts encrypted+signed (cosign), registry access-logged, no model leaves the perimeter | Egress-off; signature verify on load |
| 5 | **Explanation manipulation** | Scaffolding classifier to fool SHAP/LIME (Slack et al. 2020) | **Mitigated** — not relying solely on post-hoc; rule provenance + raw-evidence cross-check | Prefer interpretable fusion (Part 18) |
| 6 | **Supply-chain** (AML.T0048) | Malicious dependency / poisoned pretrained artifact | **Contained** — SBOM + CVE/container scan + model signing + internal mirror | Pinned deps; cosign verify |

## Residual risk & recommendations
- Low-and-slow baseline poisoning is *mitigated, not eliminated* (honest limit, Part 12/15) —
  keep long windows + periodic human-reviewed baseline resets.
- Recommend a recurring (quarterly) adversarial-ML re-test as a standing control (Part 19.5).

## Sign-off
Red Team Lead + Model Risk Committee — **2026-05-09**. Findings fed to the vuln tracker
(PLATFORM-22) and the go-live checklist (PLATFORM-41).
