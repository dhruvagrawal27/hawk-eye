# API gateway front (BACKEND-28)

`kong.yaml` is the declarative gateway config that fronts the control-plane APIs (blueprint Part 32.1).
**PLATFORM hosts the Kong/APISIX runtime**; BACKEND owns this config.

It provides, at the edge:
- **Auth** — JWT validation (defense-in-depth; the FastAPI app also validates per-route via `Depends(get_principal)`).
- **Rate-limiting** — per-route request budgets.
- **Routing** — `/api/v1` → `hawkeye-api:8000`; public `auth`/`/health`/`/metrics`; internal serving on `:8001`.
- **Observability** — Prometheus plugin + correlation-id header (`X-Request-Id`).
- **Reliability** — active upstream health checks (Part 32.2).

APISIX equivalents: `jwt-auth`, `limit-req`, `prometheus`, `request-id`. Validate with
`kong config -c kong.yaml parse` (or `deck gateway validate`) in the PLATFORM CI.
