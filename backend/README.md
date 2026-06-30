# Hawk-Eye — BACKEND (Laptop 03)

The FastAPI control plane + Rust hot-path tier for the insider-fraud system. **ALERT-ONLY**: it
scores, explains, and *requests* a block — a human decides. It never auto-blocks money and never
auto-classifies fraud. On-prem, local-first, **synthetic data only**.

The integration contract every other laptop binds to is [`../BACKEND.md`](../BACKEND.md) (owned here).

## Layout

```
backend/
├── services/api/app/        # FastAPI control plane
│   ├── main.py  config.py    observability/   # BACKEND-1
│   ├── auth/                 # OIDC/JWT (BACKEND-2) + RBAC 8×9 / SoD / OPA / case-scope (BACKEND-3)
│   ├── schemas/              # Pydantic contracts (BACKEND-4)
│   ├── routes/               # the /api/v1 surface (BACKEND-8/19/20/21/22/26/29 + auth/narrative)
│   ├── pii/                  # tokenizer + re-id vault + field crypto (BACKEND-17/18)
│   ├── pipeline/online.py    # online topology reference (BACKEND-13)
│   ├── workflow/escalation.py# SLA/TAT + routing (BACKEND-23)
│   ├── audit/                # WORM audit writer (BACKEND-22)
│   ├── clients/              # DATA/ML/DATABASE seam clients (stubs)
│   └── store/                # in-memory repositories + synthetic seed
├── rules_engine/            # L1 rules/BRE + SoD matrix + privileged (BACKEND-5/6/7)
├── serving/                 # ONNX serving + registry-driven signed loader + canary (BACKEND-9/16)
├── fusion/                  # L6 fusion: calibration + TreeSHAP + reason codes (BACKEND-12)
├── reliability/             # idempotency, circuit breaker, retry, DLQ, degradation (BACKEND-14/15)
├── regulatory/              # EWS/RFA/CRILC/FMR/CFR + slow-lane (BACKEND-24/25)
├── integrations/siem.py     # bi-directional SIEM (BACKEND-27, SCAFFOLD)
├── compliance/dpdp.py       # cross-border/DPDP (BACKEND-29, SCAFFOLD)
├── gateway/                 # Rust hot-path crate (BACKEND-10/11/14/15)
├── gateway_config/kong.yaml # API gateway front (BACKEND-28)
├── deploy/                  # compose + Dockerfiles + topology (BACKEND-13)
└── tests/                   # unit / integration / contract
```

## Run

```bash
# API (control plane) on :8000
python run_api.py                 # or: uvicorn app.main:app --app-dir services/api --port 8000
# Model serving on :8001
uvicorn serving.server:app --port 8001
# Rust hot-path gateway on :8081
cd gateway && cargo run --release --bin gateway
```

Health: `GET /health` · Metrics: `GET /metrics` (Prometheus) · Docs: `GET /api/v1/docs`.

### Local auth (synthetic)
`POST /api/v1/auth/login` with one of the seeded users (password `hawk-eye`):
`EMP-an01` analyst · `EMP-sr01` senior · `EMP-tl01` lead · `EMP-co01` compliance ·
`EMP-au01` auditor · `EMP-me01` model-engineer · `EMP-pa01` admin · `svc-ingest` service.

## Checks

```bash
ruff check . && black --check . && mypy .     # Python lint/format/type
pytest -q                                     # 102 unit + integration + contract tests
cd gateway && cargo fmt --check && cargo clippy -- -D warnings && cargo test   # Rust
```

> Local dev was validated on Python 3.13 / FastAPI 0.135 (newer patch than the Part 24.3 pins of
> 3.12 / 0.115); `pyproject.toml` declares the blueprint target pins. ruff/black/mypy/cargo are run
> in the PLATFORM CI harness. See `docs/laptops/03-backend.md` for the full deviation log.
