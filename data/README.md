# Hawk-Eye — DATA workstream

The data backbone: L0 unified event model, synthetic agent-based simulator, streaming/feature substrate, source connectors (mock), the full feature catalogue (Part 6), dataset & label sourcing, and data governance/quality/lineage. **Local-first, synthetic-only, alert-only.**

## Run it
```bash
# from repo root — no third-party install needed beyond numpy/pandas/pyarrow
python -m data.sim.cli --employees 150 --days 10      # -> data/out/<run>/{events,labels}.{parquet,jsonl}
python -m data.tests.run                              # stdlib test runner (pytest not required)
```

`pip install -e data/` is optional; heavy infra (Kafka/Flink/Feast/Redis/ClickHouse/SDV/Snorkel/featuretools/GE) is in optional extras and **guarded** — every module runs on numpy/pandas/pyarrow alone via pure-python fallbacks. Modules that need a live external system are marked **SCAFFOLD**; human/legal stand-ins are **MOCK**.

## Layout (owner: DATA / branch `hawk-eye/data`)
| Dir | Tasks | What |
|---|---|---|
| `schemas/` | DATA-1 | L0 event model (`l0_event.py` + `.avsc` + `sample_event.json`), `label.py` |
| `config.py`, `eventbus.py` | DATA-3/5 | IDs/topics/conventions; in-process bus + JSONL/Parquet/Kafka sinks |
| `sim/` | DATA-7..11 | population, normal-behaviour, **12 fraud-typology** injectors (8 fast + 4 slow), labels, simulator, augment, CLI |
| `infra/kafka/`, `streaming/`, `ingest/` | DATA-3/4/5/16/17 | topics+clients, Flink windows, normalizer, SWIFT↔CBS recon, reliability/dedupe/DLQ, count-recon |
| `connectors/` | DATA-13/14/15/18 | CBS/payments/IAM-PAM/DLP-DBaudit/HR-IGA/real-telemetry adapters + mock fixtures (SCAFFOLD) |
| `features/` | DATA-19..22 | three-way baselines + every 6.1–6.6 feature + slow-lane features + DFS |
| `datasets/`, `labels/` | DATA-12/24/23 | public-dataset loaders, temporal/entity-disjoint splits + leakage removal, 4-source label store |
| `registry/`, `feature_store/`, `governance/`, `mdm/`, `lineage/` | DATA-2/6/25/26/27 | schema registry+compat, Feast/online store, catalog/classification/quality/retention, MDM, lineage |
| `tests/` | — | `python -m data.tests.run` (90 tests) |

## Status
M1–M5 implemented & tested (90 passing). Connectors + real-telemetry are **SCAFFOLD** (await live feeds); the label store is **MOCK** for gold cases and stubs **EDD label-source-4** against `BACKEND.md` §5 until BACKEND's disposition endpoint lands. See `docs/laptops/01-data.md` for the per-task status roll-up and validations.
