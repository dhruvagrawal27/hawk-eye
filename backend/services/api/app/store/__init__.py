"""In-memory stores / repositories (BACKEND).

# STUB: DATABASE (Postgres cases/users/rules/vault + ClickHouse event/score history).
These are deterministic in-memory shims that honour the BACKEND.md contract so the API and the
online path run locally on synthetic data. Each store exposes the same method surface a real
repository would, so swapping in DATABASE's Postgres/ClickHouse needs no route change.
"""
