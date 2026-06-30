"""Alembic environment for Hawk-Eye Postgres (DATABASE-2).

DB URL resolution (never hardcode creds — golden rule 2):
  1. ``DATABASE_URL`` if set, else
  2. composed from ``POSTGRES_*`` env (defaults match deploy/compose/.env).

Supports offline ``--sql`` mode (emit DDL without a live DB) so migration
reversibility can be linted in CI without standing up Postgres.
"""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "hawkeye")
    pw = os.getenv("POSTGRES_PASSWORD", "hawkeye_dev_pw")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "hawkeye")
    return f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{db}"


config.set_main_option("sqlalchemy.url", _database_url())

# All Hawk-Eye app/metadata tables live in the `hawkeye` schema (namespaced away
# from BACKEND/PLATFORM objects in `public`/`governance`).
TARGET_SCHEMA = "hawkeye"


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=TARGET_SCHEMA,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Ensure the namespace exists before the version table is created.
        from sqlalchemy import text

        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=None,
            version_table_schema=TARGET_SCHEMA,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
