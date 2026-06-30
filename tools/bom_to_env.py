#!/usr/bin/env python3
"""Generate deploy/compose/.env image pins from the canonical BOM.

PLATFORM-1 (blueprint Part 24.3). This is what makes deploy/versions.bom.yaml the
single source of truth: compose files reference ${*_IMAGE} vars, and those vars are
generated here from the BOM. `make bom-env` regenerates; CI `bom-drift` verifies the
committed .env matches the BOM (fails the build on drift).

Usage:
    python tools/bom_to_env.py            # write deploy/compose/.env
    python tools/bom_to_env.py --check    # exit 1 if .env is stale vs the BOM
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is in the platform venv
    sys.stderr.write("PyYAML required: pip install pyyaml\n")
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
BOM = ROOT / "deploy" / "versions.bom.yaml"
ENV = ROOT / "deploy" / "compose" / ".env"

# BOM dotted-path -> compose env var. Keeps the env file flat and explicit.
MAPPING: dict[str, str] = {
    "stack.kafka.image": "KAFKA_IMAGE",
    "stack.flink.image": "FLINK_IMAGE",
    "stack.clickhouse.image": "CLICKHOUSE_IMAGE",
    "stack.redis.image": "REDIS_IMAGE",
    "stack.postgres.image": "POSTGRES_IMAGE",
    "stack.python.image": "PYTHON_IMAGE",
    "stack.triton.image": "TRITON_IMAGE",
    "stack.keycloak.image": "KEYCLOAK_IMAGE",
    "stack.mlflow.image": "MLFLOW_IMAGE",
    "stack.airflow.image": "AIRFLOW_IMAGE",
    "stack.prometheus.image": "PROMETHEUS_IMAGE",
    "stack.grafana.image": "GRAFANA_IMAGE",
    "stack.opa.image": "OPA_IMAGE",
    "stack.node.image": "NODE_IMAGE",
    "infra_extra.schema_registry.image": "SCHEMA_REGISTRY_IMAGE",
    "infra_extra.minio.image": "MINIO_IMAGE",
    "infra_extra.vault.image": "VAULT_IMAGE",
    "infra_extra.otel_collector.image": "OTEL_IMAGE",
    "infra_extra.alertmanager.image": "ALERTMANAGER_IMAGE",
    "infra_extra.spire_server.image": "SPIRE_SERVER_IMAGE",
    "infra_extra.spire_agent.image": "SPIRE_AGENT_IMAGE",
    "infra_extra.argocd.image": "ARGOCD_IMAGE",
    "infra_extra.http_echo_stub.image": "HTTP_ECHO_IMAGE",
}


def _dig(data: dict, dotted: str):
    cur = data
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def render() -> str:
    bom = yaml.safe_load(BOM.read_text())
    lines = [
        "# AUTO-GENERATED from deploy/versions.bom.yaml by tools/bom_to_env.py",
        "# Do NOT edit by hand. Run `make bom-env` to regenerate.",
        f"# BOM version: {bom['meta']['bom_version']}  (blueprint {bom['meta']['blueprint_ref']})",
        "",
    ]
    for dotted, var in MAPPING.items():
        lines.append(f"{var}={_dig(bom, dotted)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    check = "--check" in sys.argv
    content = render()
    if check:
        if not ENV.exists() or ENV.read_text() != content:
            sys.stderr.write(
                "BOM DRIFT: deploy/compose/.env is stale or missing. Run `make bom-env`.\n"
            )
            return 1
        print("BOM ok: deploy/compose/.env matches versions.bom.yaml")
        return 0
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.write_text(content)
    print(f"Wrote {ENV.relative_to(ROOT)} ({len(MAPPING)} image pins from the BOM)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
