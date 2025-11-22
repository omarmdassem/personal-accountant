# alembic/env.py
# isort: skip_file
# ruff: noqa: E402
"""
Alembic config + environment.

Goals:
- Use the application's DATABASE_URL (from .env via app.config.get_settings()).
- Ensure autogenerate sees all SQLModel tables by importing app.models.
- Work reliably with SQLite (dev) and later PostgreSQL (prod).

Usage:
  alembic revision -m "..." --autogenerate
  alembic upgrade head
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# --- Ensure project root is importable BEFORE importing app.* ---------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # repo root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Now it's safe to import from the app package
from app.config import get_settings  # reads .env
import app.models  # noqa: F401  # <-- important: registers all models in SQLModel.metadata

# Alembic Config object (reads alembic.ini)
config = context.config

# Logging (optional but helpful)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata Alembic uses for autogenerate
target_metadata = SQLModel.metadata

# Pull DB URL from app settings and inject into Alembic config
settings = get_settings()
if settings.database_url:
    config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations without a DB connection (generates SQL)."""
    url = config.get_main_option("sqlalchemy.url") or settings.database_url
    if not url:
        raise RuntimeError("No database URL configured for Alembic (offline).")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # detect column type changes
        compare_server_default=True,  # detect server default changes
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a real DB connection."""
    # Build engine from Alembic config (already patched with our app URL)
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # future kwargs could go here
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,  # safer ALTERs on SQLite
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
