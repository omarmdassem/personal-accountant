# isort: skip_file
# ruff: noqa: E402
# alembic/env.py
# Zweck: Alembic sagt der DB, welche Tabellen/Spalten existieren (SQLModel.metadata),
# und nutzt die App-DB-URL aus app.config (kein doppelter Eintrag).

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel  # enthält das "Metadata" aller SQLModel-Tabellen

# --- Pfad so setzen, dass "import app...." zuverlässig klappt ---
ROOT = Path(__file__).resolve().parents[1]  # .../your-project
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Jetzt können wir App-Module importieren (nach sys.path-Anpassung):
from app.config import get_settings

# Alembic-Konfiguration (liest u.a. alembic.ini)
config = context.config

# Logging (optional, nützlich bei Fehlersuche)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dieses Metadata beschreibt alle Tabellen der App
target_metadata = SQLModel.metadata

# DB-URL dynamisch aus der App-Konfiguration setzen
# Vorteil: nur EIN Ort für die DB-URL (.env) statt Dublette in alembic.ini
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Migrationen ohne echte DB-Verbindung (nur SQL erzeugen)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrationen gegen eine echte DB-Verbindung ausführen."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
