# Hawk-Eye — Real-Time Insider & Privileged-User Fraud Detection

> 👉 **New here / non-technical? Start with [`GETTING_STARTED.md`](GETTING_STARTED.md)** — a plain-English guide
> to what this is, how to run it in 2 minutes, how it works, and a glossary of every term.

A production-shaped, on-prem, **alert-only** insider-fraud detection platform for a public-sector bank, built local-first on **synthetic data**. Source of truth for *what* to build: [`Insider_Fraud_Detection_Implementation_Blueprint (2).md`](Insider_Fraud_Detection_Implementation_Blueprint%20(2).md) (34 parts). Source of truth for *how / in what order*: [`BUILD_PLAN.md`](BUILD_PLAN.md) (6 workstreams → 149 tasks).

## Golden rules (every laptop, every task)
1. **Alert-only.** The system scores and explains; a human decides. **It never auto-blocks money.**
2. **On-prem + synthetic.** No real bank systems, no cloud creds, no real PII. Everything runs locally on the synthetic simulator + public datasets. Real feeds/creds/hardware are **SCAFFOLD**; human/legal/hardware acts are **MOCK**.
3. **Validate against the blueprint.** No task is "done" until the matching blueprint Part's requirement is met. Cite the Part in your commits and your laptop log.
4. **Nothing is dropped.** The 6 workstreams partition the entire blueprint. If you find a blueprint requirement that isn't in your task list or anyone else's, raise it in `CONTEXT.md` immediately.

## The 6 workstreams (one laptop each)
| # | Workstream | Owns dir(s) | Prompt |
|---|---|---|---|
| 1 | 📥 **DATA** — data & ingestion | `data/` | [prompts/01_DATA.md](prompts/01_DATA.md) |
| 2 | 🤖 **ML** — models & MLOps | `ml/` | [prompts/02_ML.md](prompts/02_ML.md) |
| 3 | ⚙️ **BACKEND** — services & API | `backend/` + owns `BACKEND.md` | [prompts/03_BACKEND.md](prompts/03_BACKEND.md) |
| 4 | 🖥️ **FRONTEND** — dashboard | `frontend/` | [prompts/04_FRONTEND.md](prompts/04_FRONTEND.md) |
| 5 | 🗄️ **DATABASE** — storage | `db/` | [prompts/05_DATABASE.md](prompts/05_DATABASE.md) |
| 6 | 🏗️ **PLATFORM** — infra/security/governance/ops | `platform/`, `infra/`, `.github/`, root `docker-compose.yml` | [prompts/06_PLATFORM.md](prompts/06_PLATFORM.md) |

## The four kinds of coordination MD files
- **[`CONTEXT.md`](CONTEXT.md)** — shared full context. **Everyone appends** decisions, interfaces, and integration notes here.
- **[`BACKEND.md`](BACKEND.md)** — the backend/integration **contract** (event schema, alert schema, API routes, RBAC, score/reason-code shapes). **Owned by the BACKEND laptop**; everyone else **reads** it to integrate.
- **[`TODO.md`](TODO.md)** — shared task board. Each laptop keeps its rows current.
- **`docs/laptops/<NN-workstream>.md`** — each laptop's **own** working log (decisions, files created, deviations, blockers).

## Repo layout
```
data/        ML-ready synthetic data, simulator, L0 schema, connectors, features (DATA laptop)
ml/          models L2–L6, training, eval, mlops, explainability, LLM gateway (ML laptop)
backend/     FastAPI, L1 rules, fusion service, serving, EDD loop, tokenization, reports (BACKEND laptop)
frontend/    React/TS investigator dashboard (FRONTEND laptop)
db/          ClickHouse/Postgres/Redis/object-store/WORM/registry schemas & config (DATABASE laptop)
infra/       docker-compose, k8s, terraform (PLATFORM laptop)
platform/    security, governance mocks, observability, DR, ops (PLATFORM laptop)
tests/       cross-workstream integration tests (PLATFORM laptop owns harness; all contribute)
docs/        coordination docs + per-laptop logs
prompts/     the 6 build prompts (one per laptop)
```

## Merge model
Each laptop works on branch `hawk-eye/<workstream>` and only edits files **under its owned dirs** + its own laptop log + appends to shared MD files. Merges to `main` integrate cleanly because ownership is disjoint. Cross-workstream interfaces are agreed in `BACKEND.md` / `CONTEXT.md` **before** coding against them.
