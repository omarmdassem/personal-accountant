from __future__ import annotations

import logging
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# SQLite needs a special connect arg; others (e.g., Postgres) don't.
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    echo=False,  # set True to see SQL in console
    connect_args=connect_args,
)

# Log which DB URL is actually in use (helps avoid “which app.db?” confusion).
logger = logging.getLogger("db")
logger.info("DB URL in use: %s", engine.url)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session and closes it afterwards."""
    with Session(engine) as session:
        yield session


def create_db_and_tables() -> None:
    """
    Optional helper for ad-hoc local setups.
    Prefer Alembic migrations for schema changes.
    """
    SQLModel.metadata.create_all(engine)
