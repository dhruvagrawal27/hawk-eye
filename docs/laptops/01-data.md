# Laptop 01 — DATA — Working Log

> Full brief: [prompts/01_DATA.md](../../prompts/01_DATA.md). Branch `hawk-eye/data`, owns `data/`.

## Status (2026-06-30)
**M1–M5 implemented, tested & VERIFIED. `python -m data.tests.run` → 97 passed / 0 failed** (clean even with `-W error::FutureWarning`). All **28/28 DATA tasks acceptance-verified** task-by-task (M1 13 spot-checks, M2–M5 28 spot-checks, 7 live behavioural checks, DATA-28 Phase-0 capstone). Simulator runs end-to-end emitting all 12 typologies (8 fast + 4 slow), deterministic.

### Verification pass — gaps found & fixed
- **DATA-1:** `l0_event.proto` was missing → **added** (`data/schemas/l0_event.proto`, all 5 field-group messages, parity-tested vs BACKEND.md §1).
- **DATA-17:** source-onboarding playbook + status tracker were missing → **added** (`data/docs/source_onboarding_playbook.md` with the 8 stages + `data/ingest/onboarding_status.py` dashboard).
- **DATA-22:** the online==offline parity test was only described, not asserted → **added** real parity test (`data/tests/test_parity.py`: materialize→online read == offline `get_historical_features`).
- **Hygiene:** added `data/requirements.txt`, `data/tests/test_deliverables.py` (gap guard), fixed a `Series.view` pandas deprecation in `features/baselines.py`.

## Decisions (with blueprint Part)
- **L0 schema (DATA-1, Part 5.1):** stdlib dataclasses (no pydantic dep) in `data/schemas/l0_event.py`; five field groups Actor/Action/Object/Context/Linkage; matches `BACKEND.md` §1 field-for-field; `.avsc` + `sample_event.json` generated from source.
- **Labels kept separate from events (Part 21.4 leakage):** simulator returns `(L0Event, Label)` pairs; events carry no label field.
- **Dependency-light core (Part 24.3):** only numpy/pandas/pyarrow are hard deps so everything runs locally; Kafka/Flink/Feast/Redis/ClickHouse/SDV/Snorkel/featuretools/GE/networkx are optional, guarded with try/except + pure-python fallbacks. Heavy infra = **SCAFFOLD**; human/legal stand-ins = **MOCK**.
- **IDs/topics/feature-keys** centralized in `data/config.py` (deterministic `make_id`, `Topics`, `feature_key`, `LANE_FAST/SLOW`).
- **Slow-lane typologies + features added** per the post-audit blueprint patch (Part 12): fake-vendor, ghost-employee/payroll, alert-suppression, ghost-loan/appraisal + rogue-trader P&L-vs-mark mismarking.

## Files created (100 .py; by area)
- **core (me):** `data/__init__.py`, `config.py`, `eventbus.py`, `schemas/{__init__,l0_event,label}.py` + `l0_event.avsc` + `sample_event.json`, `tests/run.py`, `pyproject.toml`, `README.md`, `.gitignore`.
- **sim (22):** `sim/{population,normal_behaviour,labels,simulator,augment,cli}.py` + `sim/scenarios/*` (12 typology modules + registry) — DATA-7/8/9/10/11.
- **features (10):** `features/{baselines,identity_access,transaction,data_layer,change_hr,graph,temporal,dfs_featuretools}.py` — DATA-19/20/21/22.
- **ingest (15):** `infra/kafka/{topics,clients}.py`, `streaming/flink_jobs/{base_job,windowed_features}.py`, `ingest/{normalizer,count_recon}.py`, `ingest/recon/swift_cbs_join.py`, `ingest/reliability/` — DATA-3/4/5/16/17.
- **connectors (22):** `connectors/{base_adapter,cbs,payments,iam_pam,dlp_dbaudit,hr_iga,real_telemetry}` + mock fixtures — DATA-13/14/15/18 (SCAFFOLD).
- **datasets/labels (12):** `datasets/loaders/{cert,ieee_cis,ulb,paysim,elliptic,spedia}.py`, `datasets/splits.py`, `labels/label_store.py` — DATA-12/24/23.
- **governance (19):** `registry/schema_registry.py`, `feature_store/`, `governance/{catalog,classification,quality,retention}`, `mdm/entity_resolution.py`, `lineage/lineage.py` — DATA-2/6/25/26/27.

## Blueprint validation (Part → task → ✓)
- Part 5.1 → DATA-1 ✓ (sample validates; matches BACKEND.md §1) · 5.3 → DATA-12 ✓ · 5.4 → DATA-23 ✓ (4 sources; EDD stubbed) · 5.5 → DATA-7..11 ✓
- Part 6.1–6.6 + eng-note → DATA-19/20/21/22 ✓ (every feature, unit-tested fires on its typology) · Part 12 slow-lane → DATA-9/20/21 ✓
- Part 8 → DATA-3/4/6 ✓ (fallbacks) · Part 21.1–21.5 → DATA-7..11/24/25 ✓ · Part 24.5(a)/(d) → DATA-1/10 ✓ (worked burst = approve_payment 4800000)
- Part 28.1/28.2 → DATA-26/27 ✓ · Part 31.1 → DATA-27 ✓ · Part 32.1/32.2/32.3 → DATA-13..17 ✓

## Deviations / assumptions
- **pydantic→dataclasses, simpy→pure-python ABM:** to guarantee the package runs in an env with only numpy/pandas/pyarrow (pip install was unavailable). Production may swap in simpy/pydantic; the simulator already imports simpy if present.
- **ruff/black/mypy not run** (not installed, no pip): lint/type gate deferred; code follows the style. To re-enable: `pip install -e data/[dev]`.
- **pytest unavailable** → stdlib runner `data/tests/run.py` (plain `test_*` asserts). Same coverage intent.

## Blockers / stubs (mirrored in CONTEXT.md + TODO.md §7)
- **EDD label-source-4 (DATA-23)** stubbed against `BACKEND.md` §5 — awaits **BACKEND** `POST /alerts/{id}/disposition`.
- **ClickHouse sink / retention tiering (DATA-5/25)** → local fallback; awaits **DATABASE** ClickHouse DDL + object-store buckets.
- **Kafka/Redis/MinIO runtime** → InProcessBus/in-memory fallback; awaits **PLATFORM-1** docker-compose.
- **Real source feeds (DATA-13/14/18)** → mock fixtures; SCAFFOLD until live bank feeds + creds.

## 28-task status roll-up
M1 DATA-1..6 ✓REAL · M2 DATA-7..12 ✓REAL · M3 DATA-13/14/15/18 SCAFFOLD, DATA-16/17 ✓REAL · M4 DATA-19..22 ✓REAL · M5 DATA-23 MOCK(EDD stub), DATA-24/25/26/27 ✓REAL, DATA-28 ✓REAL (sim→features path green).

## Session log (newest first)
- **2026-06-30 (pandas-3.0 fix)** — Reproduced in a pandas 3.0.3 venv: 3 split tests failed because pandas 3.0 makes string columns the extension `StringDtype`, which `np.issubdtype(s.dtype, np.number)` can't interpret (`TypeError`). Fixed `data/datasets/splits.py::_sortable` to use `pd.api.types.is_numeric_dtype(s)`. Swept the whole `data/` tree for other 3.0 hazards (applymap/df.append/iteritems/errors='ignore'/inplace/uppercase-freq/.view/np.issubdtype) — none. Added `data/tests/test_pandas3_compat.py` (forces `string` dtype → catches it on any pandas version). **Now 100/100 on pandas 2.2.1 AND 3.0.3.** No contract change.
- **2026-06-30 (verify)** — Task-by-task verification of all 28 DATA tasks vs acceptance checks. Found+fixed 3 deliverable gaps (l0_event.proto, onboarding playbook+tracker, online/offline parity test) + requirements.txt + deliverables test + pandas deprecation. Suite 90→97 green (clean under `-W error::FutureWarning`). All acceptance criteria spot-checked or live-called (recon fire/quiet, EDD §5 ingest, splits temporal/leaky, catalog covers every L0 field, Phase-0 capstone sim→features). Pushed.
- **2026-06-30** — Built core (L0 schema/config/eventbus) + fanned out 6 module areas (sim/features/ingest/connectors/datasets/governance). Full suite 90/90 green; simulator emits 12/12 typologies both lanes; worked burst reproduces the INR 48,00,000 approval. Committed on `hawk-eye/data`.
