"""Service map / status (BACKEND ops).

One endpoint that tells the UI EVERY platform service, WHERE it's used in the app, whether it's
required, and its live status (probed cheaply, never raising). Powers the Admin "Service Map" panel
so an operator can see at a glance what's running and what each service is for.
"""

from __future__ import annotations

import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends

from app.auth.deps import require_capability
from app.auth.principal import Principal
from app.config import settings
from app.schemas.common import Capability

router = APIRouter(tags=["services"])

_HTTP_TIMEOUT = 1.5
_TCP_TIMEOUT = 1.0


def _http_up(url: str, path: str = "/") -> bool:
    try:
        import httpx

        r = httpx.get(url.rstrip("/") + path, timeout=_HTTP_TIMEOUT)
        return r.status_code < 500
    except Exception:  # noqa: BLE001
        return False


def _tcp_up(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=_TCP_TIMEOUT):
            return True
    except Exception:  # noqa: BLE001
        return False


def _hostport(url: str, default_port: int) -> tuple[str, int]:
    # accepts host:port, scheme://host:port, redis://…, bolt://…
    if "://" in url:
        u = urlparse(url)
        return (u.hostname or "localhost", u.port or default_port)
    if ":" in url:
        h, _, p = url.partition(":")
        return (h or "localhost", int(p) if p.isdigit() else default_port)
    return (url or "localhost", default_port)


def _near_ai_up() -> bool:
    try:
        import httpx

        base = (settings_near_base()).rstrip("/")
        r = httpx.get(f"{base}/attestation/report", params={"model": "openai/gpt-oss-120b"}, timeout=3.0)
        return r.status_code < 500
    except Exception:  # noqa: BLE001
        return False


def settings_near_base() -> str:
    import os

    return os.environ.get("NEAR_AI_BASE_URL", "https://cloud-api.near.ai/v1")


def _svc(key, name, purpose, used_by, required, why, status) -> dict:
    return {
        "key": key, "name": name, "purpose": purpose, "used_by": used_by,
        "required": required, "why": why, "status": status,
    }


@router.get("/services/status")
def services_status(
    principal: Principal = Depends(require_capability(Capability.VIEW_AUDIT)),
) -> dict:
    """Catalog + live status of every platform service (probed with short timeouts)."""
    ch_h, ch_p = _hostport(settings.clickhouse_url, 8123)
    kb_h, kb_p = _hostport(settings.kafka_bootstrap, 9092)
    rd_h, rd_p = _hostport(settings.redis_url, 6379)
    pg_h, pg_p = _hostport(settings.postgres_dsn, 5432)
    nj_h, nj_p = _hostport(settings.neo4j_uri, 7687)
    mn_h, mn_p = _hostport(settings.minio_endpoint, 9000)

    def optstat(up: bool) -> str:
        return "up" if up else "optional"

    services = [
        _svc("near_ai", "NEAR AI Cloud (TEE)", "Confidential-compute narrative + real Intel TDX attestation",
             "Narrative gateway · ProvenanceBadge (GET /narratives/{id}/attestation)", True,
             "", "up" if _near_ai_up() else "down"),
        _svc("groq", "Groq", "LLM narrative fallback (fast, non-TEE)",
             "Narrative gateway failover", True, "",
             "up" if _http_up("https://api.groq.com", "/openai/v1/models") else "down"),
        _svc("clickhouse", "ClickHouse", "Score/event time-series (durable history)",
             "ScoreOverTime history · live stream (store/score_history)",
             settings.clickhouse_enabled,
             "" if settings.clickhouse_enabled else "Optional: score-history falls back to in-memory when disabled.",
             "up" if _http_up(settings.clickhouse_url, "/ping") else optstat(False)),
        _svc("postgres", "PostgreSQL", "Durable alert/case store",
             "Alert persistence (store/persistence)", bool(settings.db_url),
             "" if settings.db_url else "Optional: in-memory store is the default (HAWKEYE_DB_URL unset).",
             "up" if _tcp_up(pg_h, pg_p) else optstat(False)),
        _svc("kafka", "Kafka", "Event bus for the online scoring stream",
             "Live stream in kafka mode (stream/engine)", settings.stream_mode == "kafka",
             "" if settings.stream_mode == "kafka" else "Optional: in-process stream is the default mode.",
             "up" if _tcp_up(kb_h, kb_p) else optstat(False)),
        _svc("redis", "Redis", "Online feature store + stream fan-out",
             "Feature reader · kafka-mode WS bridge", settings.feast_redis_enabled or settings.stream_mode == "kafka",
             "Optional: feature reader uses a deterministic shim; enable for the online store.",
             "up" if _tcp_up(rd_h, rd_p) else optstat(False)),
        _svc("serving", "Model serving (Triton)", "L2/L3 model inference",
             "Scoring pipeline (clients/serving_client)", True,
             "In-process runtime by default; real httpx→Triton seam via HAWKEYE_SERVING_URL.",
             "in_process"),
        _svc("mlflow", "MLflow", "Model registry / experiment tracking",
             "Model Engineer registry (clients/registry_client)", settings.mlflow_enabled,
             "" if settings.mlflow_enabled else "Optional: in-process registry is the source of truth; mirror to MLflow when enabled.",
             "up" if _http_up(settings.mlflow_uri, "/health") else optstat(False)),
        _svc("minio", "MinIO / S3", "Object store (model artifacts, audit archive)",
             "Artifact store (store/artifact_store)", settings.minio_enabled,
             "" if settings.minio_enabled else "Optional: artifacts kept locally in the pilot; enable for object storage.",
             "up" if _tcp_up(mn_h, mn_p) else optstat(False)),
        _svc("neo4j", "Neo4j", "Graph database for relational detection",
             "L5 graph / collusion (store/graph_db; in-process graph default)", settings.neo4j_enabled,
             "" if settings.neo4j_enabled else "Optional: the L5 graph runs in-process; enable Neo4j for a persistent graph.",
             "up" if _tcp_up(nj_h, nj_p) else optstat(False)),
        _svc("grafana", "Grafana", "Operations dashboards",
             "Admin embed (GrafanaEmbed)", False,
             "Optional: ops observability; the app functions without it.",
             "up" if _http_up("http://localhost:3000", "/api/health") else optstat(False)),
        _svc("prometheus", "Prometheus", "Metrics scrape target",
             "GET /metrics (hawkeye_* counters/histograms)", False,
             "Optional: metrics are exposed regardless; Prometheus stores them.",
             "up" if _http_up("http://localhost:9090", "/-/healthy") else optstat(False)),
        _svc("keycloak", "Keycloak", "OIDC identity provider",
             "Login in OIDC mode (auth)", settings.auth_mode == "keycloak",
             "" if settings.auth_mode == "keycloak" else "Optional: local dev-JWT auth is the pilot default.",
             "up" if _http_up(settings.keycloak_base_url, "/realms/master") else optstat(False)),
    ]
    up = sum(1 for s in services if s["status"] in ("up", "in_process"))
    return {"services": services, "up": up, "total": len(services)}
