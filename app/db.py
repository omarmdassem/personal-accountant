# app/db.py
# Purpose: provide a database engine and a short-lived Session for each request.
from sqlmodel import (  # Session = DB conversation; engine = DB connection factory
    Session,
    create_engine,
)

from app.config import get_settings  # read DB URL from .env

settings = get_settings()  # load settings once

# create the engine (connector to the DB)
# If you change the URL in .env, the app talks to a different DB file/server.
engine = create_engine(
    settings.database_url,
    echo=settings.echo_sql,  # True = logs SQL (useful for debug; slower)
    connect_args=(
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
    # above: SQLite needs this flag for multi-threaded use in dev; other DBs ignore it
)


def get_session():
    """
    Yield a short-lived Session.
    - 'yield' means FastAPI can auto-close it after the request.
    - If you forget to close sessions, you can leak connections.
    """
    with Session(engine) as session:
        yield session
