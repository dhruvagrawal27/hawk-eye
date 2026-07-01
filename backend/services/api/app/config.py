"""Settings / config module (BACKEND-1, blueprint Part 24.2/24.3).

Single typed settings object loaded from environment (.env). Secrets default to clearly
labelled local-dev placeholders; PLATFORM custodies real secrets in Vault. ON-PREM + SYNTHETIC.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings (env-prefixed ``HAWKEYE_`` where applicable)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App / transport (BACKEND-1) ---
    env: Literal["local", "ci", "staging", "prod"] = Field("local", alias="HAWKEYE_ENV")
    api_host: str = Field("0.0.0.0", alias="HAWKEYE_API_HOST")
    api_port: int = Field(8000, alias="HAWKEYE_API_PORT")
    api_base_path: str = Field("/api/v1", alias="HAWKEYE_API_BASE_PATH")
    log_level: str = Field("INFO", alias="HAWKEYE_LOG_LEVEL")
    # mTLS is terminated by the PLATFORM mesh/gateway; the API advertises the requirement and
    # records it on /health. JSON-over-HTTPS + mTLS-internal per Part 24.2 (l.891).
    mtls_internal: bool = Field(True, alias="HAWKEYE_MTLS_INTERNAL")
    service_name: str = "hawk-eye-api"

    # --- Auth (BACKEND-2) ---
    auth_mode: Literal["local", "keycloak"] = Field("local", alias="HAWKEYE_AUTH_MODE")
    dev_jwt_secret: str = Field("dev-only-change-me", alias="HAWKEYE_DEV_JWT_SECRET")
    jwt_issuer: str = Field("hawk-eye", alias="HAWKEYE_JWT_ISSUER")
    access_token_ttl_seconds: int = Field(900, alias="HAWKEYE_ACCESS_TOKEN_TTL_SECONDS")
    refresh_token_ttl_seconds: int = Field(43200, alias="HAWKEYE_REFRESH_TOKEN_TTL_SECONDS")
    keycloak_base_url: str = Field("http://localhost:8080", alias="HAWKEYE_KEYCLOAK_BASE_URL")
    keycloak_realm: str = Field("hawk-eye", alias="HAWKEYE_KEYCLOAK_REALM")
    keycloak_client_id: str = Field("hawk-eye-api", alias="HAWKEYE_KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str = Field("", alias="HAWKEYE_KEYCLOAK_CLIENT_SECRET")

    # --- PII tokenization (BACKEND-17/18) ---
    pii_hmac_key: str = Field("local-synthetic-hmac-key-change-me", alias="PII_HMAC_KEY")
    pii_field_key: str = Field(
        "local-synthetic-fernet-key-change-me", alias="HAWKEYE_PII_FIELD_KEY"
    )

    # --- Model serving + registry (BACKEND-9/16) ---
    serving_url: str = Field("http://localhost:8001", alias="HAWKEYE_SERVING_URL")
    serving_require_signature: bool = Field(True, alias="HAWKEYE_SERVING_REQUIRE_SIGNATURE")
    model_registry_url: str = Field("http://localhost:5000", alias="HAWKEYE_MODEL_REGISTRY_URL")

    # --- Narrative gateway (BACKEND-20; ML owns narrate()) ---
    narrative_url: str = Field("http://localhost:8002/narrate", alias="HAWKEYE_NARRATIVE_URL")
    # When False (local/CI), skip the HTTP call to ML's gateway and render the deterministic
    # template directly (the UI never breaks). Set True in prod where the ML gateway is reachable.
    narrative_remote_enabled: bool = Field(False, alias="HAWKEYE_NARRATIVE_REMOTE")
    # HTTP timeout for the gateway call. The gateway runs a 2-LLM failover chain
    # (NEAR AI primary -> Groq) so a real call can take several seconds; 2s was a
    # stub-era value that timed out the moment a live LLM was wired in.
    narrative_timeout_seconds: float = Field(15.0, alias="HAWKEYE_NARRATIVE_TIMEOUT")

    # --- Realtime stream (BACKEND-13 online topology; powers /ws/alerts) ---
    # off       = no stream (WS accepts but emits nothing)
    # inprocess = an asyncio replay loop scores synthetic events via ONLINE and broadcasts (no brokers)
    # kafka     = consume the events topic, score, publish to Redis, fan out to WS (production)
    stream_mode: str = Field("inprocess", alias="HAWKEYE_STREAM_MODE")
    stream_rate: float = Field(6.0, alias="HAWKEYE_STREAM_RATE")  # events/sec in inprocess mode
    kafka_events_topic: str = Field("hawkeye.events.l0", alias="HAWKEYE_KAFKA_EVENTS_TOPIC")
    redis_stream_channel: str = Field("hawkeye.stream", alias="HAWKEYE_REDIS_CHANNEL")
    # kafka_bootstrap / redis_url live in the Downstream-stores block below (shared).

    # --- Downstream stores (DATABASE owns DDL) ---
    # Persistence toggle for the alert store: "" = in-memory (default); sqlite:///path = durable
    # local; postgresql://… = Postgres (psycopg). Empty keeps the current in-memory behaviour.
    db_url: str = Field("", alias="HAWKEYE_DB_URL")
    clickhouse_url: str = Field("http://localhost:8123", alias="HAWKEYE_CLICKHOUSE_URL")
    # When 1, the online stream persists scored events to ClickHouse (durable score-history);
    # otherwise score-history is in-memory only. Guarded — CH being down never breaks scoring.
    clickhouse_enabled: bool = Field(False, alias="HAWKEYE_CLICKHOUSE_ENABLED")
    postgres_dsn: str = Field(
        "postgresql://hawkeye:hawkeye@localhost:5432/hawkeye", alias="HAWKEYE_POSTGRES_DSN"
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="HAWKEYE_REDIS_URL")
    kafka_bootstrap: str = Field("localhost:9092", alias="HAWKEYE_KAFKA_BOOTSTRAP")

    # --- Regulatory (BACKEND-24/25 — SCAFFOLD) ---
    rbi_submission_enabled: bool = Field(False, alias="HAWKEYE_RBI_SUBMISSION_ENABLED")

    # --- SLA (BACKEND-23, RBI ≤30-day, Part 33.3) ---
    sla_days_default: int = 30

    @property
    def is_local(self) -> bool:
        return self.env in ("local", "ci")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (one instance per process)."""
    return Settings()


settings = get_settings()
